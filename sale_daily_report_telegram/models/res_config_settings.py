# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sale_daily_report_telegram_enabled = fields.Boolean(
        string="Send Daily Sales Report",
        config_parameter='sale_daily_report_telegram.enabled',
        default=True,
    )
    sale_daily_report_telegram_weekly_enabled = fields.Boolean(
        string="Send Weekly Sales Report",
        config_parameter='sale_daily_report_telegram.weekly_enabled',
        default=True,
    )
    sale_daily_report_telegram_chat_id = fields.Char(
        string="Daily Sales Report Telegram Chat ID",
        config_parameter='sale_daily_report_telegram.chat_id',
        help="Telegram chat ID(s) that receive the daily sales PDF report "
             "(e.g. the bosses' personal chats). Separate multiple IDs with "
             "a comma to send to more than one recipient. The bot token "
             "itself is configured in the Send by Telegram settings."
    )
