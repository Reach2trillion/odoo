# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    attendance_telegram_report_enabled = fields.Boolean(
        string="Send Daily Attendance Report",
        config_parameter='attendance_telegram_report.enabled',
        default=True,
    )
    attendance_telegram_chat_id = fields.Char(
        string="Attendance Report Telegram Chat ID",
        config_parameter='attendance_telegram_report.chat_id',
        help="Telegram chat/group ID that receives the daily attendance report. "
             "The bot token itself is configured in the Send by Telegram settings."
    )
