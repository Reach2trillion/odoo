# -*- coding: utf-8 -*-
import logging
import re
from datetime import datetime


from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command

from .telegram_tools import TelegramError

_logger = logging.getLogger(__name__)

NUMERIC_CHAT_ID_RE = re.compile(r'^-?\d+$')


class TelegramChat(models.Model):
    _name = 'telegram.chat'
    _description = 'Telegram Chat'
    _inherit = ['mail.thread']
    _order = 'last_message_date desc nulls last, id desc'
    _rec_names_search = ['name', 'username', 'chat_id', 'partner_id.name']

    name = fields.Char(compute='_compute_name', store=True, readonly=False)
    active = fields.Boolean(default=True)
    bot_id = fields.Many2one(
        'telegram.bot', string='Bot', required=True, ondelete='cascade', index=True,
        default=lambda self: self.env['telegram.bot'].search([], limit=1))
    company_id = fields.Many2one(related='bot_id.company_id', store=True)
    chat_id = fields.Char(
        string='Telegram Chat ID', required=True, index=True,
        help="Numeric Telegram identifier (negative for groups and channels). "
             "You can also type @username and click 'Refresh Info'.")
    chat_type = fields.Selection([
        ('private', 'Private chat'),
        ('group', 'Group'),
        ('supergroup', 'Supergroup'),
        ('channel', 'Channel'),
    ], string='Type', default='private', required=True)
    title = fields.Char(string='Group / Channel Title')
    first_name = fields.Char()
    last_name = fields.Char()
    username = fields.Char(string='Telegram Username')
    language_code = fields.Char(string='Language')

    partner_id = fields.Many2one('res.partner', string='Contact', tracking=True, index=True)
    tag_ids = fields.Many2many(
        'telegram.chat.tag', 'telegram_chat_tag_rel', 'chat_id', 'tag_id', string='Tags')
    subscribed = fields.Boolean(
        default=True, tracking=True,
        help="Receives marketing campaigns. Switched off automatically when the customer sends /stop.")
    blocked = fields.Boolean(
        tracking=True,
        help="The customer blocked the bot, or the bot was removed from the group or channel. "
             "Telegram refuses messages to this chat.")
    start_payload = fields.Char(
        string='Start Parameter', readonly=True,
        help="Deep-link parameter received with /start, e.g. the 'shop' in https://t.me/yourbot?start=shop. "
             "Useful to know where a subscriber came from.")

    telegram_message_ids = fields.One2many('telegram.message', 'chat_id', string='Telegram Messages')
    telegram_message_count = fields.Integer(compute='_compute_message_count')
    last_message_date = fields.Datetime(string='Last Message', readonly=True, index=True)
    last_inbound_date = fields.Datetime(string='Last Customer Message', readonly=True)
    last_message_preview = fields.Char(string='Last Message Preview', readonly=True)
    unread_count = fields.Integer(string='Unread', readonly=True, default=0)

    conversation_html = fields.Html(string='Conversation', compute='_compute_conversation_html', sanitize=False)
    reply_text = fields.Text(string='Reply')
    reply_attachment = fields.Binary(string='Attachment')
    reply_attachment_name = fields.Char(string='Attachment Name')

    _sql_constraints = [
        ('bot_chat_uniq', 'unique(bot_id, chat_id)', 'This chat already exists for this bot.'),
    ]

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends('title', 'first_name', 'last_name', 'username', 'chat_id', 'chat_type')
    def _compute_name(self):
        for chat in self:
            full_name = ' '.join(part for part in (chat.first_name, chat.last_name) if part)
            if chat.chat_type != 'private' and chat.title:
                chat.name = chat.title
            else:
                chat.name = (full_name or chat.title or (chat.username and '@%s' % chat.username)
                             or chat.chat_id or _('Telegram chat'))

    @api.depends('name', 'username', 'chat_type')
    def _compute_display_name(self):
        for chat in self:
            if chat.username and chat.chat_type == 'private' and chat.name != '@%s' % chat.username:
                chat.display_name = '%s (@%s)' % (chat.name, chat.username)
            else:
                chat.display_name = chat.name or ''

    def _compute_message_count(self):
        counts = {chat.id: count for chat, count in self.env['telegram.message']._read_group(
            [('chat_id', 'in', self.ids)], ['chat_id'], ['__count'])}
        for chat in self:
            chat.telegram_message_count = counts.get(chat.id, 0)

    def _compute_conversation_html(self):
        for chat in self:
            chat.conversation_html = chat._render_conversation() if isinstance(chat.id, int) else False

    @api.model
    def mail_allowed_qweb_expressions(self):
        """Placeholders every Telegram user may use in campaigns and automatic messages
        (anything else requires the Mail Template Editor group)."""
        return tuple(super().mail_allowed_qweb_expressions()) + (
            'object.name',
            'object.first_name',
            'object.last_name',
            'object.username',
            'object.title',
            'object.chat_id',
            'object.language_code',
            'object.start_payload',
            'object.partner_id.name',
            'object.partner_id.ref',
            'object.partner_id.phone',
            'object.partner_id.mobile',
            'object.partner_id.email',
            'object.partner_id.city',
            'object.partner_id.commercial_company_name',
            'object.bot_id.name',
            'object.bot_id.username',
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._clean_identifiers(vals)
        chats = super().create(vals_list)
        chats._sync_partner_username()
        return chats

    def write(self, vals):
        self._clean_identifiers(vals)
        result = super().write(vals)
        if vals.get('partner_id') or vals.get('username'):
            self._sync_partner_username()
        return result

    @api.model
    def _clean_identifiers(self, vals):
        if vals.get('username'):
            vals['username'] = vals['username'].strip().lstrip('@')
        if vals.get('chat_id'):
            vals['chat_id'] = str(vals['chat_id']).strip()

    def _sync_partner_username(self):
        for chat in self:
            partner = chat.partner_id
            if partner and chat.username and not partner.telegram_username:
                partner.sudo().write({'telegram_username': chat.username})

    # ------------------------------------------------------------------
    # Synchronisation with Telegram
    # ------------------------------------------------------------------

    @api.model
    def _get_or_create_from_telegram(self, bot, chat_data, from_data=None, contact=None):
        """Find or create the record for a Telegram ``Chat`` object, updating names on the way.

        ``contact`` is the Telegram ``Contact`` object shared with the message, if any: it helps
        matching an existing customer by phone number.
        """
        chat_id = str(chat_data.get('id'))
        chat_type = chat_data.get('type') or 'private'
        if chat_type not in dict(self._fields['chat_type'].selection):
            chat_type = 'private'
        values = {
            'chat_type': chat_type,
            'title': chat_data.get('title') or False,
            'username': (chat_data.get('username') or '').lstrip('@') or False,
            'first_name': chat_data.get('first_name') or False,
            'last_name': chat_data.get('last_name') or False,
        }
        if chat_type == 'private' and from_data and from_data.get('language_code'):
            values['language_code'] = from_data['language_code']

        chat = self.with_context(active_test=False).search(
            [('bot_id', '=', bot.id), ('chat_id', '=', chat_id)], limit=1)
        if chat:
            changed = {key: value for key, value in values.items() if (chat[key] or False) != (value or False)}
            if not chat.active:
                changed['active'] = True
            if changed:
                chat.write(changed)
            return chat

        values.update({'bot_id': bot.id, 'chat_id': chat_id})
        chat = self.with_context(mail_create_nolog=True, mail_create_nosubscribe=True).create(values)
        chat._auto_link_partner(contact=contact)
        return chat

    @api.model
    def _get_or_create_manual(self, bot, identifier):
        """Resolve '@channel', '-1001234567890' or '123456789' through getChat."""
        identifier = (identifier or '').strip()
        if not identifier:
            raise UserError(_("Enter a chat ID or a @username."))
        domain = [('bot_id', '=', bot.id)]
        if NUMERIC_CHAT_ID_RE.match(identifier):
            existing = self.with_context(active_test=False).search(domain + [('chat_id', '=', identifier)], limit=1)
        else:
            identifier = '@' + identifier.lstrip('@')
            existing = self.with_context(active_test=False).search(
                domain + [('username', '=ilike', identifier[1:])], limit=1)
        if existing:
            return existing
        try:
            info = bot._api_call('getChat', {'chat_id': identifier})
        except TelegramError as exc:
            raise UserError(_(
                "Telegram does not know the chat '%(chat)s': %(error)s\n"
                "The bot must be a member (for channels: an administrator) before it can post there, "
                "and a customer must have started the bot before it can write to them.",
                chat=identifier, error=exc))
        return self._get_or_create_from_telegram(bot, info)

    def _auto_link_partner(self, contact=None):
        """Link a private chat to a contact: by Telegram username, by shared phone number, or create one."""
        Partner = self.env['res.partner'].sudo().with_context(mail_create_nolog=True, mail_create_nosubscribe=True)
        phone_number = (contact or {}).get('phone_number') or ''
        for chat in self.filtered(lambda c: not c.partner_id and c.chat_type == 'private'):
            partner = Partner.browse()
            if chat.username:
                partner = Partner.search([('telegram_username', '=ilike', chat.username)], limit=1)
            if not partner and phone_number:
                partner = self._find_partner_by_phone(phone_number)
            if not partner and chat.bot_id.auto_create_partner:
                contact_name = ' '.join(part for part in (
                    (contact or {}).get('first_name'), (contact or {}).get('last_name')) if part)
                partner = Partner.create({
                    'name': contact_name or chat.name or chat.chat_id,
                    'phone': phone_number or False,
                    'telegram_username': chat.username or False,
                    'comment': _("Created automatically from a Telegram chat (ID %s).", chat.chat_id),
                })
            if partner:
                chat.write({'partner_id': partner.id})

    @api.model
    def _find_partner_by_phone(self, phone_number):
        """Match a contact on the last 8 digits of its phone or mobile number (formatting-insensitive)."""
        digits = re.sub(r'\D', '', phone_number or '')
        if len(digits) < 6:
            return self.env['res.partner'].sudo().browse()
        tail = '%' + digits[-8:]
        self.env.cr.execute(r"""
            SELECT id FROM res_partner
             WHERE active
               AND (regexp_replace(COALESCE(phone, ''), '\D', '', 'g') LIKE %s
                    OR regexp_replace(COALESCE(mobile, ''), '\D', '', 'g') LIKE %s)
             ORDER BY id
             LIMIT 1
        """, (tail, tail))
        row = self.env.cr.fetchone()
        return self.env['res.partner'].sudo().browse(row[0] if row else [])

    def _match_partner_from_contact(self, contact):
        """A customer shared a phone contact: complete the linked contact, or link/create one."""
        self.ensure_one()
        phone_number = (contact or {}).get('phone_number') or ''
        if not phone_number:
            return
        if self.partner_id:
            if not self.partner_id.phone and not self.partner_id.mobile:
                self.partner_id.sudo().write({'phone': phone_number})
            return
        self._auto_link_partner(contact=contact)

    # ------------------------------------------------------------------
    # Message hooks
    # ------------------------------------------------------------------

    def _on_inbound_message(self, message):
        self.ensure_one()
        self.write({
            'last_message_date': message.date,
            'last_inbound_date': message.date,
            'last_message_preview': message.preview,
            'unread_count': self.unread_count + 1,
        })
        self._notify_bus(message)

    def _on_outbound_message(self, message):
        self.ensure_one()
        values = {
            'last_message_date': message.sent_date or message.date,
            'last_message_preview': message.preview,
        }
        if message.author_id and not message.campaign_id:
            values['unread_count'] = 0
        self.write(values)
        self._notify_bus(message)

    def _notify_bus(self, message):
        """Tell open web clients that this conversation changed (live conversation widget).

        The notification goes to the channel of the *Telegram / User* group: every logged-in member
        of the group is subscribed to it automatically by the web client, and nobody else can listen.
        """
        try:
            group = self.env.ref('telegram_marketing.group_telegram_user', raise_if_not_found=False)
            if not group:
                return
            self.env['bus.bus']._sendone(group, 'telegram_marketing/new_message', {
                'chat_id': self.id,
                'message_id': message.id,
                'direction': message.direction,
            })
        except Exception:  # noqa: BLE001 - a notification problem must never break message processing
            _logger.exception("Telegram: could not notify the web client")

    # ------------------------------------------------------------------
    # Conversation rendering
    # ------------------------------------------------------------------

    def _render_conversation(self, limit=200):
        self.ensure_one()
        messages = self.env['telegram.message'].search(
            [('chat_id', '=', self.id)], order='date desc, id desc', limit=limit)
        messages = messages.sorted(key=lambda m: (m.date or datetime.min, m.id))
        return self.env['ir.qweb']._render('telegram_marketing.conversation', {
            'chat': self,
            'messages': messages,
            'truncated': len(messages) >= limit,
        })

    def get_conversation_html(self):
        """RPC entry point used by the conversation widget to refresh itself."""
        self.ensure_one()
        return str(self._render_conversation())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_send_reply(self):
        self.ensure_one()
        text = (self.reply_text or '').strip()
        if not text and not self.reply_attachment:
            raise UserError(_("Type a message or attach a file first."))
        if self.blocked:
            raise UserError(_("This chat is blocked: the customer stopped the bot or the bot was removed."))
        attachment = None
        if self.reply_attachment:
            attachment = self.env['ir.attachment'].create({
                'name': self.reply_attachment_name or _('attachment'),
                'datas': self.reply_attachment,
                'res_model': self._name,
                'res_id': self.id,
            })
        message = self.env['telegram.message']._send_text(self, text, attachment=attachment, author=self.env.user)
        self.write({
            'reply_text': False,
            'reply_attachment': False,
            'reply_attachment_name': False,
            'unread_count': 0,
        })
        if message.state == 'failed':
            return self.bot_id._notification(
                _("Message not delivered"), message.error or _("Unknown error"), 'danger')
        return True

    def action_mark_read(self):
        self.filtered('unread_count').write({'unread_count': 0})
        return True

    def action_subscribe(self):
        self.write({'subscribed': True})
        return True

    def action_unsubscribe(self):
        self.write({'subscribed': False})
        return True

    def action_refresh_info(self):
        for chat in self:
            identifier = chat.chat_id if NUMERIC_CHAT_ID_RE.match(chat.chat_id or '') else '@' + (chat.chat_id or '').lstrip('@')
            try:
                info = chat.bot_id._api_call('getChat', {'chat_id': identifier})
            except TelegramError as exc:
                raise UserError(_("Telegram could not find this chat: %s", exc))
            chat.write({
                'chat_id': str(info.get('id') or chat.chat_id),
                'chat_type': info.get('type') if info.get('type') in dict(self._fields['chat_type'].selection) else chat.chat_type,
                'title': info.get('title') or False,
                'username': info.get('username') or False,
                'first_name': info.get('first_name') or False,
                'last_name': info.get('last_name') or False,
                'blocked': False,
            })
        return True

    def action_open_partner(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("No contact is linked to this chat yet."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_messages(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('telegram_marketing.telegram_message_action')
        action['domain'] = [('chat_id', '=', self.id)]
        action['context'] = {'default_chat_id': self.id, 'search_default_group_by_direction': 0}
        return action

    def action_open_compose(self):
        action = self.env['ir.actions.actions']._for_xml_id('telegram_marketing.telegram_compose_action')
        action['context'] = {
            'default_bot_id': self[:1].bot_id.id,
            'default_chat_ids': [Command.set(self.ids)],
        }
        return action
