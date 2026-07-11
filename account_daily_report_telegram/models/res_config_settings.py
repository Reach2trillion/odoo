# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    account_daily_report_telegram_enabled = fields.Boolean(
        string="Send Daily Accounting Report",
        config_parameter='account_daily_report_telegram.enabled',
        default=True,
    )
    account_daily_report_telegram_weekly_enabled = fields.Boolean(
        string="Send Weekly Accounting Report",
        config_parameter='account_daily_report_telegram.weekly_enabled',
        default=True,
    )
    account_daily_report_telegram_monthly_enabled = fields.Boolean(
        string="Send Monthly Accounting Report",
        config_parameter='account_daily_report_telegram.monthly_enabled',
        default=True,
    )
    account_daily_report_telegram_chat_id = fields.Char(
        string="Accounting Report Telegram Chat ID",
        config_parameter='account_daily_report_telegram.chat_id',
        help="Telegram chat ID(s) that receive the accounting PDF reports "
             "(e.g. the bosses' personal chats). Separate multiple IDs with "
             "a comma to send to more than one recipient. The bot token "
             "itself is configured in the Send by Telegram settings."
    )
