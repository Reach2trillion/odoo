# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services.telegram_service import TelegramService


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    telegram_bot_token = fields.Char(
        string="Telegram Bot Token",
        config_parameter='send_by_telegram.bot_token',
        help="Enter your Telegram bot token obtained from @BotFather"
    )

    # Daily attendance report
    attendance_telegram_report_enabled = fields.Boolean(
        string="Send Daily Attendance Report",
        config_parameter='send_by_telegram.attendance_report_enabled',
        default=True,
    )
    attendance_telegram_chat_id = fields.Char(
        string="Attendance Report Telegram Chat ID",
        config_parameter='send_by_telegram.attendance_report_chat_id',
        help="Telegram chat/group ID that receives the daily attendance report."
    )
    attendance_telegram_late_enabled = fields.Boolean(
        string="Send Late Attendance Alert",
        config_parameter='send_by_telegram.attendance_late_enabled',
        default=True,
    )
    attendance_telegram_late_chat_id = fields.Char(
        string="Late Alert Telegram Chat ID",
        config_parameter='send_by_telegram.attendance_late_chat_id',
        help="Telegram chat/group ID that receives the late attendance alert "
             "(e.g. the all-employees group). Leave empty to reuse the "
             "attendance report chat ID above."
    )
    attendance_telegram_late_grace_minutes = fields.Integer(
        string="Late Grace Period (minutes)",
        config_parameter='send_by_telegram.attendance_late_grace_minutes',
        default=0,
        help="Number of minutes after the scheduled start time before an "
             "employee is considered late."
    )

    # Daily sales report
    sale_daily_report_telegram_enabled = fields.Boolean(
        string="Send Daily Sales Report",
        config_parameter='send_by_telegram.sale_daily_report_enabled',
        default=True,
    )
    sale_daily_report_telegram_chat_id = fields.Char(
        string="Daily Sales Report Telegram Chat ID",
        config_parameter='send_by_telegram.sale_daily_report_chat_id',
        help="Telegram chat ID(s) that receive the daily sales PDF report, "
             "comma-separated for multiple recipients (e.g. one boss's chat, "
             "one for another)."
    )

    # Stock reports
    stock_report_telegram_enabled = fields.Boolean(
        string="Send Daily Stock Report",
        config_parameter='send_by_telegram.stock_report_enabled',
        default=True,
    )
    stock_report_telegram_monthly_enabled = fields.Boolean(
        string="Send Monthly Stock Report",
        config_parameter='send_by_telegram.stock_report_monthly_enabled',
        default=True,
    )
    stock_report_telegram_chat_id = fields.Char(
        string="Stock Report Telegram Chat ID",
        config_parameter='send_by_telegram.stock_report_chat_id',
        help="Telegram chat ID(s) that receive the stock reports, "
             "comma-separated for multiple recipients (e.g. one boss's chat, "
             "one for another)."
    )
    stock_report_telegram_location_1_id = fields.Many2one(
        'stock.location',
        string="Stock Location 1",
        config_parameter='send_by_telegram.stock_location_1_id',
        domain=[('usage', '=', 'internal')],
        help="First stock location to track (e.g. Warehouse)."
    )
    stock_report_telegram_location_2_id = fields.Many2one(
        'stock.location',
        string="Stock Location 2",
        config_parameter='send_by_telegram.stock_location_2_id',
        domain=[('usage', '=', 'internal')],
        help="Second stock location to track (e.g. Office Sale Stock)."
    )

    def action_test_telegram_bot(self):
        """Test the Telegram bot connection."""
        self.ensure_one()

        token = self.env['ir.config_parameter'].sudo().get_param(
            'send_by_telegram.bot_token'
        )

        if not token:
            raise UserError(_("Please enter a Telegram bot token first."))

        try:
            service = TelegramService(token)
            bot_info = service.test_connection()
            bot_username = bot_info.get('username', 'Unknown')

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Success!"),
                    'message': _("Bot connected successfully! Username: @%s") % bot_username,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except UserError:
            raise
        except Exception as e:
            raise UserError(_("Failed to connect to Telegram bot: %s") % str(e))
