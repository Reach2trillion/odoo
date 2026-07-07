# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    telegram_group_id = fields.Char(
        string="Telegram Group ID",
        help="Chat or group ID used to send Telegram messages to this contact.",
    )
