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
