# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sale_daily_report_telegram_enabled = fields.Boolean(
        string="Send Daily Sales Report",
        config_parameter='sale_daily_report_telegram.enabled',
        default=True,
    )
    sale_daily_report_telegram_chat_id = fields.Char(
        string="Daily Sales Report Telegram Chat ID",
        config_parameter='sale_daily_report_telegram.chat_id',
        help="Telegram chat ID that receives the daily sales PDF report "
             "(e.g. the boss's personal chat). The bot token itself is "
             "configured in the Send by Telegram settings."
    )
