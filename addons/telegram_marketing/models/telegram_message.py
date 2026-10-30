# -*- coding: utf-8 -*-
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from markupsafe import Markup

from odoo import _, api, fields, models, tools

from .telegram_tools import (
    TELEGRAM_CAPTION_LIMIT, TELEGRAM_MAX_DOWNLOAD, TELEGRAM_MAX_PHOTO, TELEGRAM_TEXT_LIMIT,
    TelegramError, escape_text, html_to_telegram, normalize_placeholders, split_text, telegram_html_to_text,
)

_logger = logging.getLogger(__name__)

SEND_DELAY = 1.0 / 25  # stay below Telegram's ~30 messages per second for broadcasts
PHOTO_MIMETYPES = ('image/jpeg', 'image/png', 'image/webp')


class TelegramMessage(models.Model):
    _name = 'telegram.message'
    _description = 'Telegram Message'
    _order = 'date desc, id desc'
    _rec_name = 'preview'

    chat_id = fields.Many2one('telegram.chat', string='Chat', required=True, ondelete='cascade', index=True)
    bot_id = fields.Many2one(related='chat_id.bot_id', store=True, index=True)
    company_id = fields.Many2one(related='chat_id.company_id', store=True)
    partner_id = fields.Many2one(related='chat_id.partner_id', store=True, string='Contact')
    direction = fields.Selection([
        ('in', 'Received'),
        ('out', 'Sent'),
    ], required=True, default='out', index=True)
    message_type = fields.Selection([
        ('text', 'Text'),
        ('photo', 'Photo'),
        ('document', 'Document'),
        ('voice', 'Voice'),
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('sticker', 'Sticker'),
        ('location', 'Location'),
        ('contact', 'Contact'),
        ('other', 'Other'),
    ], default='text', required=True)
    body = fields.Text(
        help="Received messages: plain text. Sent messages: the HTML-formatted text accepted by Telegram.")
    preview = fields.Char(compute='_compute_preview', store=True)
    attachment_id = fields.Many2one('ir.attachment', string='Attachment', ondelete='set null')
    buttons_json = fields.Text(string='Buttons (JSON)')
    disable_link_preview = fields.Boolean(string='Hide Link Preview')
    telegram_message_id = fields.Char(string='Telegram Message ID', readonly=True, index=True)
    telegram_file_id = fields.Char(string='Telegram File ID', readonly=True)
    state = fields.Selection([
        ('received', 'Received'),
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], default='queued', required=True, index=True)
    error = fields.Text(readonly=True)
    date = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    sent_date = fields.Datetime(readonly=True)
    campaign_id = fields.Many2one('telegram.campaign', string='Campaign', ondelete='set null', index=True)
    auto_reply_id = fields.Many2one('telegram.auto.reply', string='Auto Reply Rule', ondelete='set null')
    author_id = fields.Many2one('res.users', string='Sent By', readonly=True)
    is_auto = fields.Boolean(string='Automatic')
    raw_json = fields.Text(string='Raw Update', readonly=True, groups='telegram_marketing.group_telegram_manager')

    # ------------------------------------------------------------------
    # Computes / display
    # ------------------------------------------------------------------

    @api.depends('body', 'direction', 'message_type', 'attachment_id.name')
    def _compute_preview(self):
        for message in self:
            text = message.body or ''
            if message.direction == 'out':
                text = telegram_html_to_text(text)
            text = ' '.join(text.split())
            if not text and message.attachment_id:
                text = '📎 %s' % (message.attachment_id.name or '')
            elif not text:
                text = '[%s]' % message.message_type
            message.preview = text[:120]

    def _get_display_html(self):
        """HTML shown in the conversation widget (always sanitized)."""
        self.ensure_one()
        body = self.body or ''
        if self.direction == 'in':
            return tools.html_escape(body).replace('\n', Markup('<br/>'))
        return tools.html_sanitize(body.replace('\n', '<br/>'), sanitize_attributes=True, strip_style=True)

    @api.model
    def _telegram_timestamp_to_datetime(self, timestamp):
        try:
            return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).replace(tzinfo=None)
        except (TypeError, ValueError, OverflowError, OSError):
            return fields.Datetime.now()

    # ------------------------------------------------------------------
    # Incoming content
    # ------------------------------------------------------------------

    SERVICE_KEYS = (
        'new_chat_members', 'left_chat_member', 'new_chat_title', 'new_chat_photo', 'delete_chat_photo',
        'group_chat_created', 'supergroup_chat_created', 'channel_chat_created', 'pinned_message',
        'migrate_to_chat_id', 'migrate_from_chat_id', 'message_auto_delete_timer_changed',
        'video_chat_scheduled', 'video_chat_started', 'video_chat_ended', 'video_chat_participants_invited',
        'forum_topic_created', 'forum_topic_closed', 'forum_topic_reopened', 'forum_topic_edited',
        'web_app_data', 'successful_payment', 'boost_added', 'proximity_alert_triggered',
    )

    @api.model
    def _parse_incoming_content(self, message):
        """Return ``(message_type, body, file_info)`` or ``None`` for service messages."""
        caption = message.get('caption') or ''
        message_id = message.get('message_id', '')
        if message.get('text') is not None:
            return 'text', message['text'], None
        if message.get('photo'):
            sizes = [size for size in message['photo'] if isinstance(size, dict)]
            largest = max(sizes, key=lambda s: ((s.get('width') or 0) * (s.get('height') or 0), s.get('file_size') or 0))
            return 'photo', caption, {
                'file_id': largest.get('file_id'), 'name': 'photo_%s.jpg' % message_id,
                'mimetype': 'image/jpeg', 'file_size': largest.get('file_size'),
            }
        if message.get('document'):
            document = message['document']
            return 'document', caption, {
                'file_id': document.get('file_id'), 'name': document.get('file_name') or 'document_%s' % message_id,
                'mimetype': document.get('mime_type') or 'application/octet-stream', 'file_size': document.get('file_size'),
            }
        if message.get('voice'):
            voice = message['voice']
            return 'voice', caption, {
                'file_id': voice.get('file_id'), 'name': 'voice_%s.ogg' % message_id,
                'mimetype': voice.get('mime_type') or 'audio/ogg', 'file_size': voice.get('file_size'),
            }
        if message.get('audio'):
            audio = message['audio']
            return 'audio', caption, {
                'file_id': audio.get('file_id'), 'name': audio.get('file_name') or 'audio_%s.mp3' % message_id,
                'mimetype': audio.get('mime_type') or 'audio/mpeg', 'file_size': audio.get('file_size'),
            }
        video = message.get('video') or message.get('video_note') or message.get('animation')
        if video:
            return 'video', caption, {
                'file_id': video.get('file_id'), 'name': video.get('file_name') or 'video_%s.mp4' % message_id,
                'mimetype': video.get('mime_type') or 'video/mp4', 'file_size': video.get('file_size'),
            }
        if message.get('sticker'):
            emoji = message['sticker'].get('emoji') or ''
            return 'sticker', ('%s [sticker]' % emoji).strip(), None
        if message.get('location'):
            location = message['location']
            return 'location', 'https://maps.google.com/?q=%s,%s' % (
                location.get('latitude'), location.get('longitude')), None
        if message.get('venue'):
            venue = message['venue']
            location = venue.get('location') or {}
            return 'location', '%s\n%s\nhttps://maps.google.com/?q=%s,%s' % (
                venue.get('title') or '', venue.get('address') or '',
                location.get('latitude'), location.get('longitude')), None
        if message.get('contact'):
            contact = message['contact']
            return 'contact', ' '.join(part for part in (
                contact.get('first_name'), contact.get('last_name'), contact.get('phone_number')) if part), None
        if message.get('poll'):
            return 'other', '[Poll] %s' % (message['poll'].get('question') or ''), None
        if any(key in message for key in self.SERVICE_KEYS):
            return None
        if caption:
            return 'other', caption, None
        return 'other', _("[Unsupported message type]"), None

    def _download_telegram_file(self, file_info):
        """Download a received file with getFile and attach it to the message."""
        self.ensure_one()
        file_id = file_info.get('file_id')
        if not file_id:
            return False
        bot = self.chat_id.bot_id
        try:
            size = file_info.get('file_size') or 0
            if size > TELEGRAM_MAX_DOWNLOAD:
                raise TelegramError(_("File too large to download (%s MB).", round(size / 1024 / 1024, 1)))
            info = bot._api_call('getFile', {'file_id': file_id})
            file_path = (info or {}).get('file_path')
            if not file_path:
                raise TelegramError(_("Telegram did not return a file path."))
            if (info.get('file_size') or 0) > TELEGRAM_MAX_DOWNLOAD:
                raise TelegramError(_("File too large to download."))
            content = bot._download_file(file_path)
        except TelegramError as exc:
            _logger.warning("Telegram: could not download file %s: %s", file_id, exc)
            self.write({'error': str(exc)})
            return False
        attachment = self.env['ir.attachment'].sudo().create({
            'name': file_info.get('name') or file_path.rsplit('/', 1)[-1],
            'raw': content,
            'mimetype': file_info.get('mimetype'),
            'res_model': self._name,
            'res_id': self.id,
        })
        self.write({'attachment_id': attachment.id})
        return attachment

    # ------------------------------------------------------------------
    # Outgoing messages
    # ------------------------------------------------------------------

    @api.model
    def _attachment_is_photo(self, attachment):
        mimetype = (attachment.mimetype or '').lower()
        return mimetype in PHOTO_MIMETYPES and (attachment.file_size or 0) <= TELEGRAM_MAX_PHOTO

    @api.model
    def _render_html_for_chats(self, html_value, chats):
        """Render placeholders ({{ object.first_name ||| there }}) for every chat and convert to
        Telegram HTML. Returns ``{chat_id: telegram_html}``."""
        if not html_value or not chats:
            return {chat.id: '' for chat in chats}
        rendered = self.env['mail.render.mixin']._render_template(
            normalize_placeholders(html_value), 'telegram.chat', chats.ids, engine='inline_template')
        return {chat_id: html_to_telegram(value) for chat_id, value in rendered.items()}

    @api.model
    def _render_html_for_chat(self, html_value, chat):
        """Render placeholders for ``chat`` and convert to Telegram HTML."""
        return self._render_html_for_chats(html_value, chat).get(chat.id, '')

    @api.model
    def _compose(self, chat, telegram_html, attachment=None, buttons=None, campaign=None, author=None,
                 is_auto=False, auto_reply=None, disable_link_preview=False):
        """Create a queued outbound message (``telegram_html`` is already Telegram-formatted)."""
        return self.create({
            'chat_id': chat.id,
            'direction': 'out',
            'state': 'queued',
            'body': telegram_html or '',
            'message_type': ('photo' if self._attachment_is_photo(attachment) else 'document') if attachment else 'text',
            'attachment_id': attachment.id if attachment else False,
            'buttons_json': json.dumps(buttons) if buttons else False,
            'disable_link_preview': disable_link_preview,
            'campaign_id': campaign.id if campaign else False,
            'auto_reply_id': auto_reply.id if auto_reply else False,
            'author_id': author.id if author else False,
            'is_auto': is_auto,
            'date': fields.Datetime.now(),
        })

    @api.model
    def _send_html(self, chat, html_value, attachment=None, buttons=None, author=None, is_auto=False,
                   auto_reply=None, disable_link_preview=False):
        """Render an HTML message for ``chat`` and send it right away."""
        message = self._compose(
            chat, self._render_html_for_chat(html_value, chat), attachment=attachment, buttons=buttons,
            author=author, is_auto=is_auto, auto_reply=auto_reply, disable_link_preview=disable_link_preview)
        message._send()
        return message

    @api.model
    def _send_text(self, chat, text, attachment=None, author=None):
        """Send a plain text message (and/or a file) right away."""
        message = self._compose(chat, escape_text(text), attachment=attachment, author=author)
        message._send()
        return message

    def _send(self):
        """Send queued (or failed) outbound messages now.

        Delivery problems are stored on the message; a Telegram rate limit (429) re-raises
        ``TelegramError`` so that the caller can pause.
        """
        for message in self:
            if message.direction != 'out' or message.state not in ('queued', 'failed'):
                continue
            chat = message.chat_id
            if chat.blocked:
                message.write({'state': 'failed', 'error': _("The chat is blocked (the customer stopped the bot).")})
                continue
            try:
                result = message._send_via_api()
            except TelegramError as exc:
                if exc.is_rate_limited:
                    message.write({'state': 'queued', 'error': str(exc)})
                    raise
                message.write({'state': 'failed', 'error': str(exc)})
                if exc.is_unreachable_chat:
                    chat.write({'blocked': True})
                continue
            values = {'state': 'sent', 'sent_date': fields.Datetime.now(), 'error': False}
            if isinstance(result, dict) and result.get('message_id'):
                values['telegram_message_id'] = str(result['message_id'])
            message.write(values)
            chat._on_outbound_message(message)
        return True

    def _send_via_api(self):
        self.ensure_one()
        chat = self.chat_id
        bot = chat.bot_id
        base_params = {'chat_id': chat.chat_id, 'parse_mode': 'HTML'}
        reply_markup = json.loads(self.buttons_json) if self.buttons_json else None
        text = self.body or ''
        attachment = self.attachment_id
        result = None

        if attachment:
            content = attachment.raw
            if not content:
                raise TelegramError(_("The attachment is empty."))
            if self._attachment_is_photo(attachment):
                method, field_name = 'sendPhoto', 'photo'
            else:
                method, field_name = 'sendDocument', 'document'
            files = {field_name: (attachment.name or 'file', content, attachment.mimetype or 'application/octet-stream')}
            if len(text) <= TELEGRAM_CAPTION_LIMIT:
                params = dict(base_params, caption=text or None, reply_markup=reply_markup)
                return bot._api_call(method, params, files=files, timeout=120)
            # Long text: send the media first, the text follows as separate message(s).
            result = bot._api_call(method, dict(base_params), files=files, timeout=120)

        if not text:
            if result is None:
                raise TelegramError(_("Nothing to send: the message is empty."))
            return result

        chunks = split_text(text, TELEGRAM_TEXT_LIMIT)
        for index, chunk in enumerate(chunks):
            params = dict(base_params, text=chunk)
            if self.disable_link_preview:
                params['link_preview_options'] = {'is_disabled': True}
            if reply_markup and index == len(chunks) - 1:
                params['reply_markup'] = reply_markup
            result = bot._api_call('sendMessage', params)
        return result

    # ------------------------------------------------------------------
    # Queue processing (cron)
    # ------------------------------------------------------------------

    @api.model
    def _cron_send_queue(self, limit=None):
        """Launch due campaigns, then send queued messages (rate limited)."""
        Campaign = self.env['telegram.campaign']
        Campaign._cron_launch_scheduled()

        if limit is None:
            param = self.env['ir.config_parameter'].sudo().get_param('telegram_marketing.batch_size', '500')
            try:
                limit = max(1, int(param))
            except (TypeError, ValueError):
                limit = 500
        messages = self.search([('direction', '=', 'out'), ('state', '=', 'queued')], order='id asc', limit=limit)
        testing = getattr(threading.current_thread(), 'testing', False)
        retry_after = None
        for index, message in enumerate(messages, start=1):
            try:
                message._send()
            except TelegramError as exc:
                retry_after = exc.retry_after or 5
                _logger.info("Telegram: rate limited by Telegram, pausing for %s seconds", retry_after)
                break
            if not testing:
                if index % 20 == 0:
                    self.env.cr.commit()  # keep progress: messages already left for Telegram
                time.sleep(SEND_DELAY)
        if not testing:
            self.env.cr.commit()

        Campaign._update_sending_states()

        remaining = self.search_count([('direction', '=', 'out'), ('state', '=', 'queued')], limit=1)
        if remaining or retry_after:
            self._trigger_send_cron(at=fields.Datetime.now() + timedelta(seconds=retry_after or 1))
        return True

    @api.model
    def _trigger_send_cron(self, at=None):
        cron = self.env.ref('telegram_marketing.ir_cron_telegram_send_queue', raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger(at=at)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_retry(self):
        failed = self.filtered(lambda m: m.direction == 'out' and m.state in ('failed', 'cancelled'))
        failed.write({'state': 'queued', 'error': False})
        if failed:
            self._trigger_send_cron()
        return True

    def action_cancel(self):
        self.filtered(lambda m: m.direction == 'out' and m.state == 'queued').write({'state': 'cancelled'})
        return True
