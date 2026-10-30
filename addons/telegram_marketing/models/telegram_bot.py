# -*- coding: utf-8 -*-
import json
import logging
import re
import secrets
import threading
from urllib.parse import quote

import requests
from markupsafe import Markup

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError, ValidationError

from .telegram_tools import TelegramError

_logger = logging.getLogger(__name__)

DEFAULT_API_BASE = 'https://api.telegram.org'
ALLOWED_UPDATES = ['message', 'channel_post', 'my_chat_member']
TOKEN_RE = re.compile(r'^\d+:[\w-]+$')


class TelegramBot(models.Model):
    _name = 'telegram.bot'
    _description = 'Telegram Bot'
    _inherit = ['mail.thread']
    _order = 'name, id'

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=lambda self: self.env.company)
    token = fields.Char(
        string='Bot Token', copy=False, groups='telegram_marketing.group_telegram_manager',
        help="Token given by @BotFather, for example 123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    username = fields.Char(string='Bot Username', readonly=True, copy=False)
    telegram_id = fields.Char(string='Bot ID', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Not Connected'),
        ('connected', 'Connected'),
        ('error', 'Error'),
    ], default='draft', readonly=True, copy=False, tracking=True)
    connection_error = fields.Text(readonly=True, copy=False)

    update_mode = fields.Selection([
        ('webhook', 'Webhook - instant, needs a public HTTPS URL'),
        ('polling', 'Polling - every minute, works without public URL'),
    ], string='Receive Messages By', default='webhook', required=True, tracking=True)
    webhook_secret = fields.Char(
        default=lambda self: secrets.token_urlsafe(32), copy=False,
        groups='telegram_marketing.group_telegram_manager')
    webhook_url = fields.Char(
        compute='_compute_webhook_url', groups='telegram_marketing.group_telegram_manager')
    webhook_set = fields.Boolean(string='Webhook Active', readonly=True, copy=False)
    webhook_info = fields.Text(string='Webhook Details', readonly=True, copy=False)
    last_update_id = fields.Integer(string='Last Update ID', readonly=True, copy=False)

    start_link = fields.Char(string='Start Link', compute='_compute_start_link')
    start_qr_html = fields.Html(string='QR Code', compute='_compute_start_link', sanitize=False)

    auto_create_partner = fields.Boolean(
        string='Create Contacts Automatically', default=True,
        help="Create a contact for every customer who starts a private chat with the bot.")
    download_media = fields.Boolean(
        string='Download Received Files', default=True,
        help="Store photos and documents sent by customers as attachments (up to 20 MB each).")
    auto_reply_enabled = fields.Boolean(string='Automatic Replies', default=True)
    auto_reply_in_groups = fields.Boolean(
        string='Auto Reply in Groups', default=False,
        help="By default keyword rules only answer in private chats, to avoid flooding groups.")
    welcome_body = fields.Html(
        string='Welcome Message',
        default=lambda self: _(
            "<p>Hello {{ object.first_name ||| there }}! 👋<br/>"
            "Thanks for subscribing. You will receive our news and promotions right here.<br/>"
            "Send /stop at any time to unsubscribe.</p>"),
        help="Sent when a customer presses Start (/start). "
             "Placeholders such as {{ object.first_name ||| there }} are supported.")
    stop_body = fields.Html(
        string='Unsubscribe Message',
        default=lambda self: _(
            "<p>You have been unsubscribed. Send /start whenever you want to hear from us again.</p>"),
        help="Sent when a customer sends /stop.")
    default_reply_body = fields.Html(
        string='Default Reply',
        help="Optional answer sent when no auto-reply rule matches a customer message. "
             "Leave empty to stay silent and let your team answer from the Inbox.")
    auto_reply_ids = fields.One2many('telegram.auto.reply', 'bot_id', string='Auto Reply Rules')

    chat_ids = fields.One2many('telegram.chat', 'bot_id', string='Chats')
    chat_count = fields.Integer(compute='_compute_counts')
    subscriber_count = fields.Integer(compute='_compute_counts')
    telegram_message_count = fields.Integer(compute='_compute_counts')
    campaign_count = fields.Integer(compute='_compute_counts')

    _sql_constraints = [
        ('token_uniq', 'unique(token)', 'This bot token is already used by another bot.'),
    ]

    # ------------------------------------------------------------------
    # Constraints / computes
    # ------------------------------------------------------------------

    @api.constrains('token')
    def _check_token(self):
        for bot in self:
            token = bot.sudo().token
            if token and not TOKEN_RE.match(token.strip()):
                raise ValidationError(_(
                    "The token looks wrong. Copy it from @BotFather, it looks like 123456789:AAH..."))

    def _compute_counts(self):
        Chat = self.env['telegram.chat']
        chat_counts = {bot.id: count for bot, count in Chat._read_group(
            [('bot_id', 'in', self.ids)], ['bot_id'], ['__count'])}
        subscriber_counts = {bot.id: count for bot, count in Chat._read_group(
            [('bot_id', 'in', self.ids), ('subscribed', '=', True), ('blocked', '=', False),
             ('chat_type', '=', 'private')], ['bot_id'], ['__count'])}
        message_counts = {bot.id: count for bot, count in self.env['telegram.message']._read_group(
            [('bot_id', 'in', self.ids)], ['bot_id'], ['__count'])}
        campaign_counts = {bot.id: count for bot, count in self.env['telegram.campaign']._read_group(
            [('bot_id', 'in', self.ids)], ['bot_id'], ['__count'])}
        for bot in self:
            bot.chat_count = chat_counts.get(bot.id, 0)
            bot.subscriber_count = subscriber_counts.get(bot.id, 0)
            bot.telegram_message_count = message_counts.get(bot.id, 0)
            bot.campaign_count = campaign_counts.get(bot.id, 0)

    @api.depends('webhook_secret')
    def _compute_webhook_url(self):
        for bot in self:
            secret = bot.sudo().webhook_secret
            if bot.id and secret:
                bot.webhook_url = '%s/telegram/webhook/%s/%s' % (bot.get_base_url().rstrip('/'), bot.id, secret)
            else:
                bot.webhook_url = False

    @api.depends('username')
    def _compute_start_link(self):
        for bot in self:
            if bot.username:
                link = 'https://t.me/%s' % bot.username
                bot.start_link = link
                bot.start_qr_html = Markup(
                    '<img class="img img-fluid o_telegram_qr" alt="QR code" '
                    'src="/report/barcode/?barcode_type=QR&amp;value=%s&amp;width=220&amp;height=220&amp;humanreadable=0"/>'
                ) % quote(link, safe='')
            else:
                bot.start_link = False
                bot.start_qr_html = False

    # ------------------------------------------------------------------
    # Telegram Bot API client
    # ------------------------------------------------------------------

    @api.model
    def _get_api_base(self):
        base = self.env['ir.config_parameter'].sudo().get_param('telegram_marketing.api_base') or DEFAULT_API_BASE
        return base.rstrip('/')

    def _get_token(self):
        self.ensure_one()
        token = (self.sudo().token or '').strip()
        if not token:
            raise TelegramError(_("The bot '%s' has no token. Paste the token from @BotFather first.", self.name))
        return token

    def _api_call(self, method, params=None, files=None, timeout=20):
        """Call a Bot API method and return its ``result``; raise TelegramError on failure.

        ``files`` is a dict for multipart uploads ({'photo': (name, bytes, mimetype)}).
        The token is never written to logs or error messages.
        """
        self.ensure_one()
        token = self._get_token()
        url = '%s/bot%s/%s' % (self._get_api_base(), token, method)
        params = {key: value for key, value in (params or {}).items() if value is not None}
        try:
            if files:
                data = {key: json.dumps(value) if isinstance(value, (dict, list)) else value
                        for key, value in params.items()}
                response = requests.post(url, data=data, files=files, timeout=timeout)
            else:
                response = requests.post(url, json=params, timeout=timeout)
        except requests.RequestException as exc:
            raise TelegramError(_("Could not reach Telegram: %s", str(exc).replace(token, '<token>'))) from exc
        try:
            payload = response.json()
        except ValueError:
            raise TelegramError(_("Unexpected answer from Telegram (HTTP %s)", response.status_code),
                                error_code=response.status_code)
        if not isinstance(payload, dict) or not payload.get('ok'):
            parameters = (payload.get('parameters') if isinstance(payload, dict) else None) or {}
            raise TelegramError(
                (payload.get('description') if isinstance(payload, dict) else None) or _("Unknown Telegram error"),
                error_code=(payload.get('error_code') if isinstance(payload, dict) else None) or response.status_code,
                retry_after=parameters.get('retry_after'),
            )
        return payload.get('result')

    def _download_file(self, file_path, timeout=60):
        """Download a file previously located with getFile; returns bytes."""
        self.ensure_one()
        token = self._get_token()
        url = '%s/file/bot%s/%s' % (self._get_api_base(), token, file_path)
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise TelegramError(_("Could not download the file from Telegram: %s",
                                  str(exc).replace(token, '<token>'))) from exc
        return response.content

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _notification(self, title, message, notification_type='success', close=False):
        """Client action showing a toast; ``close=True`` also closes the current dialog (wizards)."""
        params = {'title': title, 'message': message, 'type': notification_type, 'sticky': False}
        if close:
            params['next'] = {'type': 'ir.actions.act_window_close'}
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': params}

    def action_check_connection(self):
        for bot in self:
            try:
                me = bot._api_call('getMe')
            except TelegramError as exc:
                bot.write({'state': 'error', 'connection_error': str(exc)})
                return self._notification(_("Connection failed"), str(exc), 'danger')
            bot.write({
                'state': 'connected',
                'connection_error': False,
                'username': me.get('username'),
                'telegram_id': str(me.get('id', '')),
            })
        return self._notification(
            _("Connected"), _("The bot @%s is reachable.", ', @'.join(name for name in self.mapped('username') if name)))

    def action_set_webhook(self):
        self.ensure_one()
        url = self.webhook_url
        if not url or not url.lower().startswith('https://'):
            raise UserError(_(
                "Telegram only accepts webhooks on a public HTTPS address. Your current base URL is %s.\n"
                "Set the 'web.base.url' system parameter to your public https:// address, "
                "or switch the bot to polling mode.", url or self.get_base_url()))
        try:
            self._api_call('setWebhook', {
                'url': url,
                'secret_token': self.sudo().webhook_secret,
                'allowed_updates': ALLOWED_UPDATES,
            })
        except TelegramError as exc:
            raise UserError(_("Telegram refused the webhook: %s", exc))
        self.write({'update_mode': 'webhook', 'webhook_set': True})
        self.action_refresh_webhook_info()
        return self._notification(_("Webhook active"), _("Telegram will now push messages to Odoo instantly."))

    def action_use_polling(self):
        self.ensure_one()
        try:
            self._api_call('deleteWebhook', {'drop_pending_updates': False})
        except TelegramError as exc:
            raise UserError(_("Could not remove the webhook: %s", exc))
        self.write({'update_mode': 'polling', 'webhook_set': False, 'webhook_info': False})
        return self._notification(_("Polling mode"), _("New messages are now fetched every minute by the scheduler."))

    def action_refresh_webhook_info(self):
        for bot in self:
            try:
                info = bot._api_call('getWebhookInfo')
            except TelegramError as exc:
                bot.write({'webhook_info': str(exc)})
                continue
            bot.write({
                'webhook_info': json.dumps(info, indent=2, ensure_ascii=False),
                'webhook_set': bool(info.get('url')),
            })
        return True

    def action_view_chats(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('telegram_marketing.telegram_chat_action')
        action['domain'] = [('bot_id', '=', self.id)]
        action['context'] = {'default_bot_id': self.id}
        return action

    def action_view_subscribers(self):
        action = self.action_view_chats()
        action['context'] = dict(action['context'], search_default_subscribed=1, search_default_private=1)
        return action

    def action_view_messages(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('telegram_marketing.telegram_message_action')
        action['domain'] = [('bot_id', '=', self.id)]
        return action

    def action_view_campaigns(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('telegram_marketing.telegram_campaign_action')
        action['domain'] = [('bot_id', '=', self.id)]
        action['context'] = {'default_bot_id': self.id}
        return action

    def action_open_compose(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('telegram_marketing.telegram_compose_action')
        action['context'] = {'default_bot_id': self.id}
        return action

    # ------------------------------------------------------------------
    # Incoming updates
    # ------------------------------------------------------------------

    def _process_update(self, update):
        """Process one Telegram update (webhook or polling). Must be called with sudo."""
        self.ensure_one()
        if not isinstance(update, dict):
            return
        update_id = update.get('update_id')
        if isinstance(update_id, int) and update_id > self.last_update_id:
            self.write({'last_update_id': update_id})
        message = update.get('message') or update.get('channel_post')
        if message:
            self._process_message(message)
        elif update.get('my_chat_member'):
            self._process_my_chat_member(update['my_chat_member'])

    def _process_message(self, message):
        self.ensure_one()
        chat_data = message.get('chat') or {}
        from_data = message.get('from') or {}
        if not chat_data.get('id'):
            return
        if from_data.get('is_bot'):
            return  # never talk to other bots (avoids loops in groups)
        Message = self.env['telegram.message'].sudo()
        parsed = Message._parse_incoming_content(message)
        if not parsed:
            return  # service message (member joined, pinned message...)
        message_type, body, file_info = parsed

        chat = self.env['telegram.chat'].sudo()._get_or_create_from_telegram(
            self, chat_data, from_data, contact=message.get('contact'))
        telegram_message_id = str(message.get('message_id', '')) or False
        if telegram_message_id and Message.search_count([
            ('chat_id', '=', chat.id), ('direction', '=', 'in'),
            ('telegram_message_id', '=', telegram_message_id),
        ], limit=1):
            return  # Telegram re-delivered an update we already stored

        received = Message.create({
            'chat_id': chat.id,
            'direction': 'in',
            'state': 'received',
            'message_type': message_type,
            'body': body,
            'telegram_message_id': telegram_message_id,
            'telegram_file_id': file_info.get('file_id') if file_info else False,
            'date': Message._telegram_timestamp_to_datetime(message.get('date')),
            'raw_json': json.dumps(message, ensure_ascii=False),
        })
        if file_info and self.download_media:
            received._download_telegram_file(file_info)
        if message.get('contact'):
            chat._match_partner_from_contact(message['contact'])
        chat._on_inbound_message(received)

        text = message.get('text') or ''
        if text.startswith('/'):
            self._handle_command(chat, received, text)
        else:
            self._handle_auto_reply(chat, received, text or message.get('caption') or '')

    def _handle_command(self, chat, received, text):
        command, _sep, payload = text.strip().partition(' ')
        command = command.split('@')[0].lower()
        Message = self.env['telegram.message'].sudo()
        if command == '/start':
            values = {'subscribed': True, 'blocked': False}
            payload = payload.strip()
            if payload:
                values['start_payload'] = payload[:64]
            chat.write(values)
            if self._has_content(self.welcome_body):
                Message._send_html(chat, self.welcome_body, is_auto=True)
            return True
        if command in ('/stop', '/unsubscribe'):
            chat.write({'subscribed': False})
            if self._has_content(self.stop_body):
                Message._send_html(chat, self.stop_body, is_auto=True)
            return True
        return False

    def _handle_auto_reply(self, chat, received, text):
        if not self.auto_reply_enabled or not text.strip():
            return False
        if chat.chat_type != 'private' and not self.auto_reply_in_groups:
            return False
        if chat.blocked:
            return False
        for rule in self.auto_reply_ids:
            if rule._matches(text):
                rule._send_reply(chat)
                return True
        if self._has_content(self.default_reply_body):
            self.env['telegram.message'].sudo()._send_html(chat, self.default_reply_body, is_auto=True)
            return True
        return False

    def _process_my_chat_member(self, data):
        """The bot was blocked/unblocked by a user, or added to/removed from a group or channel."""
        self.ensure_one()
        chat_data = data.get('chat') or {}
        new_status = (data.get('new_chat_member') or {}).get('status')
        if not chat_data.get('id') or not new_status:
            return
        from_data = data.get('from') if chat_data.get('type') == 'private' else None
        chat = self.env['telegram.chat'].sudo()._get_or_create_from_telegram(self, chat_data, from_data)
        if new_status in ('kicked', 'left'):
            chat.write({'blocked': True})
        elif new_status in ('member', 'administrator', 'creator', 'restricted'):
            chat.write({'blocked': False})

    @api.model
    def _has_content(self, html_value):
        return bool(html_value and tools.html2plaintext(html_value).strip())

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    @api.model
    def _cron_poll_updates(self):
        bots = self.sudo().search([('update_mode', '=', 'polling'), ('token', '!=', False)])
        testing = getattr(threading.current_thread(), 'testing', False)
        for bot in bots:
            for _iteration in range(10):
                try:
                    updates = bot._api_call('getUpdates', {
                        'offset': bot.last_update_id + 1 if bot.last_update_id else None,
                        'limit': 100,
                        'timeout': 0,
                        'allowed_updates': ALLOWED_UPDATES,
                    }, timeout=30)
                except TelegramError as exc:
                    if exc.error_code == 409:
                        # A webhook is still registered on Telegram's side: remove it so polling can work.
                        try:
                            bot._api_call('deleteWebhook')
                        except TelegramError:
                            pass
                    _logger.warning("Telegram bot %s: getUpdates failed: %s", bot.name, exc)
                    bot.write({'connection_error': str(exc)})
                    break
                if bot.connection_error:
                    bot.write({'connection_error': False})
                for update in updates or []:
                    try:
                        with self.env.cr.savepoint():
                            bot._process_update(update)
                    except Exception:  # noqa: BLE001 - one bad update must not block the others
                        _logger.exception("Telegram bot %s: error while processing update %s",
                                          bot.name, update.get('update_id'))
                        update_id = update.get('update_id')
                        if isinstance(update_id, int) and update_id > bot.last_update_id:
                            bot.write({'last_update_id': update_id})
                if not testing:
                    self.env.cr.commit()  # keep the offset even if a later bot fails
                if not updates or len(updates) < 100:
                    break
        return True
