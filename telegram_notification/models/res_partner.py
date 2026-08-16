# Part of the telegram_notification module. License LGPL-3.
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    telegram_username = fields.Char(string='Telegram Username', compute='_compute_telegram_info')
    telegram_link = fields.Char(string='Telegram', compute='_compute_telegram_info')

    def _compute_telegram_info(self):
        for partner in self:
            user = partner._telegram_user()
            partner.telegram_username = user.telegram_username if user else False
            partner.telegram_link = 'https://t.me/%s' % user.telegram_username \
                if user and user.telegram_username else False

    def _telegram_user(self):
        """ Return the user linked to a Telegram account for this partner,
            falling back on the commercial partner (e.g. when the order uses
            a delivery or invoice child address). """
        self.ensure_one()
        for partner in (self, self.commercial_partner_id):
            user = partner.sudo().user_ids.filtered(lambda u: u.active and u.telegram_uid)[:1]
            if user:
                return user
        return None

    def _telegram_chat_id(self):
        """ In a private conversation, the chat id equals the user's Telegram id. """
        self.ensure_one()
        user = self._telegram_user()
        return user.telegram_uid if user else False
