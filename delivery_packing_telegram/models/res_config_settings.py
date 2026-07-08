# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    delivery_packing_telegram_default_group_id = fields.Char(
        string="Default Packing Telegram Group ID",
        config_parameter='delivery_packing_telegram.default_group_id',
        help="Used for delivery operation types that don't have their own "
             "Telegram Group ID configured (Inventory > Configuration > "
             "Operation Types).",
    )
