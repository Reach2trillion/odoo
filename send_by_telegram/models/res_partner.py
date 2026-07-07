# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    telegram_group_id = fields.Char(
        string="Telegram Group ID",
        help="Telegram group/chat ID where messages will be sent. "
             "The bot must be added to this group as an administrator."
    )
