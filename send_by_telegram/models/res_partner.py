# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    telegram_group_id = fields.Char(
        string="Telegram Group ID",
        help="Telegram group/chat ID where messages will be sent. "
             "The bot must be added to this group as an administrator. "
             "If empty, messages fall back to the default group configured "
             "in Settings (e.g. for website customers)."
    )

    @api.model
    def _get_telegram_fallback_group_id(self):
        """Default group used when a partner has no Telegram Group ID
        (typical for website/e-commerce customers)."""
        return (self.env['ir.config_parameter'].sudo().get_param(
            'send_by_telegram.default_group_id') or '').strip()

    def _get_telegram_chat_id(self):
        """The chat to send this partner's messages to: the partner's own
        group if set, otherwise the configured fallback group ('' if neither)."""
        self.ensure_one()
        own = (self.telegram_group_id or '').strip()
        return own or self._get_telegram_fallback_group_id()
