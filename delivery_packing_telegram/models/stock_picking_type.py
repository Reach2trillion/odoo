# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    telegram_group_id = fields.Char(
        string="Telegram Group ID",
        help="Telegram group/chat ID to notify with the packing list when a "
             "sale order confirms a delivery of this operation type. Leave "
             "empty to use the default group set in Settings > Inventory.",
    )
