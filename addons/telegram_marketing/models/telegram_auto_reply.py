# -*- coding: utf-8 -*-
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TelegramAutoReply(models.Model):
    _name = 'telegram.auto.reply'
    _description = 'Telegram Auto Reply Rule'
    _order = 'sequence, id'

    name = fields.Char(string='Rule', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    bot_id = fields.Many2one(
        'telegram.bot', string='Bot', required=True, ondelete='cascade', index=True,
        default=lambda self: self.env['telegram.bot'].search([], limit=1))
    company_id = fields.Many2one(related='bot_id.company_id', store=True)
    keywords = fields.Char(
        required=True,
        help="Comma-separated keywords, in any language. Example: price, តម្លៃ, how much\n"
             "For regular expressions: one expression per line.")
    match_type = fields.Selection([
        ('contains', 'Message contains a keyword'),
        ('exact', 'Message equals a keyword'),
        ('starts', 'Message starts with a keyword'),
        ('regex', 'Regular expression'),
    ], default='contains', required=True)
    reply_body = fields.Html(string='Reply', required=True)
    attachment = fields.Binary(string='Image or File', attachment=True)
    attachment_filename = fields.Char()
    button_text = fields.Char(string='Button Text', help="Optional link button shown under the reply.")
    button_url = fields.Char(string='Button Link')
    hit_count = fields.Integer(string='Times Used', readonly=True)

    @api.constrains('button_text', 'button_url')
    def _check_button(self):
        for rule in self:
            if bool(rule.button_text) != bool(rule.button_url):
                raise ValidationError(_("A button needs both a text and a link."))
            if rule.button_url and not re.match(r'^(https?://|tg://)', rule.button_url, re.I):
                raise ValidationError(_("Button links must start with http://, https:// or tg://"))

    @api.constrains('keywords', 'match_type')
    def _check_keywords(self):
        for rule in self:
            if not rule._get_keywords():
                raise ValidationError(_("Enter at least one keyword."))
            if rule.match_type == 'regex':
                for keyword in rule._get_keywords():
                    try:
                        re.compile(keyword)
                    except re.error as exc:
                        raise ValidationError(_("Invalid regular expression '%(regex)s': %(error)s",
                                                regex=keyword, error=exc))

    def _get_keywords(self):
        self.ensure_one()
        if self.match_type == 'regex':
            # one regular expression per line (commas are meaningful in a regex)
            return [part.strip() for part in (self.keywords or '').splitlines() if part.strip()]
        return [part.strip().casefold() for part in (self.keywords or '').replace('\n', ',').split(',') if part.strip()]

    def _matches(self, text):
        self.ensure_one()
        if not text:
            return False
        normalized = ' '.join(text.casefold().split())
        for keyword in self._get_keywords():
            if self.match_type == 'contains' and keyword in normalized:
                return True
            if self.match_type == 'exact' and normalized == keyword:
                return True
            if self.match_type == 'starts' and normalized.startswith(keyword):
                return True
            if self.match_type == 'regex':
                try:
                    if re.search(keyword, text, re.IGNORECASE):
                        return True
                except re.error:
                    continue
        return False

    def _send_reply(self, chat):
        self.ensure_one()
        attachment = None
        if self.attachment:
            attachment = self.env['ir.attachment'].sudo().create({
                'name': self.attachment_filename or _('attachment'),
                'datas': self.attachment,
                'res_model': self._name,
                'res_id': self.id,
            })
        buttons = None
        if self.button_text and self.button_url:
            buttons = {'inline_keyboard': [[{'text': self.button_text, 'url': self.button_url}]]}
        message = self.env['telegram.message'].sudo()._send_html(
            chat, self.reply_body, attachment=attachment, buttons=buttons, is_auto=True, auto_reply=self)
        self.sudo().write({'hit_count': self.hit_count + 1})
        return message
