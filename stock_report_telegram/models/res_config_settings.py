# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    stock_report_telegram_enabled = fields.Boolean(
        string="Send Daily Stock Report",
        config_parameter='stock_report_telegram.enabled',
        default=True,
    )
    stock_report_telegram_monthly_enabled = fields.Boolean(
        string="Send Monthly Stock Report",
        config_parameter='stock_report_telegram.monthly_enabled',
        default=True,
    )
    stock_report_telegram_chat_id = fields.Char(
        string="Stock Report Telegram Chat ID",
        config_parameter='stock_report_telegram.chat_id',
        help="Telegram chat ID(s) that receive the stock reports (e.g. the "
             "bosses' personal chats). Separate multiple IDs with a comma "
             "to send to more than one recipient. The bot token itself is "
             "configured in the Send by Telegram settings."
    )
    stock_report_telegram_location_1_id = fields.Many2one(
        'stock.location',
        string="Stock Location 1",
        config_parameter='stock_report_telegram.location_1_id',
        domain=[('usage', '=', 'internal')],
        help="First stock location to track (e.g. Warehouse)."
    )
    stock_report_telegram_location_2_id = fields.Many2one(
        'stock.location',
        string="Stock Location 2",
        config_parameter='stock_report_telegram.location_2_id',
        domain=[('usage', '=', 'internal')],
        help="Second stock location to track (e.g. Office Sale Stock)."
    )
