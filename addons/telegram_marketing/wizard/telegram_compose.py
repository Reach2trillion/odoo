# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command


class TelegramCompose(models.TransientModel):
    _name = 'telegram.compose'
    _description = 'Send Telegram Message'

    bot_id = fields.Many2one(
        'telegram.bot', string='Bot', required=True,
        default=lambda self: self.env['telegram.bot'].search([('state', '=', 'connected')], limit=1)
        or self.env['telegram.bot'].search([], limit=1))
    chat_ids = fields.Many2many('telegram.chat', string='Recipients')
    manual_chat_id = fields.Char(
        string='Other Chat',
        help="Send to any chat the bot can reach even if it is not listed yet: a @channel, a @group "
             "or a numeric chat ID (for example -1001234567890).")
    body = fields.Html(string='Message')
    attachment = fields.Binary(string='Image or File')
    attachment_filename = fields.Char()
    button_text = fields.Char(string='Button Text')
    button_url = fields.Char(string='Button Link')
    disable_preview = fields.Boolean(string='Hide Link Previews')
    recipient_count = fields.Integer(compute='_compute_recipient_count')

    @api.depends('chat_ids', 'manual_chat_id')
    def _compute_recipient_count(self):
        for wizard in self:
            wizard.recipient_count = len(wizard.chat_ids) + (1 if (wizard.manual_chat_id or '').strip() else 0)

    @api.constrains('button_text', 'button_url')
    def _check_button(self):
        for wizard in self:
            if bool(wizard.button_text) != bool(wizard.button_url):
                raise ValidationError(_("A button needs both a text and a link."))
            if wizard.button_url and not re.match(r'^(https?://|tg://)', wizard.button_url, re.I):
                raise ValidationError(_("Button links must start with http://, https:// or tg://"))

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        context = self.env.context
        active_model = context.get('active_model')
        active_ids = context.get('active_ids') or ([context['active_id']] if context.get('active_id') else [])
        chats = self.env['telegram.chat']
        if active_model == 'telegram.chat' and active_ids:
            chats = chats.browse(active_ids).exists()
        elif active_model == 'res.partner' and active_ids:
            chats = self.env['res.partner'].browse(active_ids).exists().telegram_chat_ids
        chats = chats.filtered(lambda c: not c.blocked)
        if chats and 'chat_ids' in fields_list and not result.get('chat_ids'):
            result['chat_ids'] = [Command.set(chats.ids)]
        if chats and 'bot_id' in fields_list and not context.get('default_bot_id'):
            result['bot_id'] = chats[0].bot_id.id
        return result

    def action_send(self):
        self.ensure_one()
        Message = self.env['telegram.message']
        if not self.bot_id._has_content(self.body) and not self.attachment:
            raise UserError(_("Write a message or attach a file first."))
        chats = self.chat_ids.filtered(lambda c: not c.blocked)
        if (self.manual_chat_id or '').strip():
            chats |= self.env['telegram.chat']._get_or_create_manual(self.bot_id, self.manual_chat_id)
        if not chats:
            raise UserError(_("Choose at least one recipient."))
        if chats.filtered(lambda c: c.bot_id != self.bot_id):
            raise UserError(_("All recipients must belong to the bot %s.", self.bot_id.name))

        attachment = None
        if self.attachment:
            attachment = self.env['ir.attachment'].create({
                'name': self.attachment_filename or _('attachment'),
                'datas': self.attachment,
                'res_model': 'telegram.bot',
                'res_id': self.bot_id.id,
            })
        buttons = None
        if self.button_text and self.button_url:
            buttons = {'inline_keyboard': [[{'text': self.button_text, 'url': self.button_url}]]}

        messages = Message
        for chat in chats:
            messages |= Message._compose(
                chat, Message._render_html_for_chat(self.body, chat), attachment=attachment, buttons=buttons,
                author=self.env.user, disable_link_preview=self.disable_preview)
        if len(messages) <= 20:
            try:
                messages._send()
            except Exception:  # noqa: BLE001 - rate limit: the scheduler will take over
                Message._trigger_send_cron()
        else:
            Message._trigger_send_cron()

        failed = messages.filtered(lambda m: m.state == 'failed')
        sent = messages.filtered(lambda m: m.state == 'sent')
        queued = messages.filtered(lambda m: m.state == 'queued')
        if failed and len(messages) == 1:
            return self.bot_id._notification(_("Message not delivered"), failed.error or '', 'danger', close=True)
        summary = _("%(sent)s sent, %(failed)s failed, %(queued)s queued for the scheduler.",
                    sent=len(sent), failed=len(failed), queued=len(queued))
        return self.bot_id._notification(_("Telegram"), summary, 'warning' if failed else 'success', close=True)
