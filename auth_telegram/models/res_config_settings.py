# Part of the auth_telegram module. License LGPL-3.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    auth_telegram_bot_username = fields.Char(
        string="Telegram Bot Username",
        config_parameter='auth_telegram.bot_username',
        help="Username of your Telegram bot, without the leading @ (e.g. my_company_bot). "
             "The bot must be linked to your website domain with @BotFather's /setdomain command.")
    auth_telegram_bot_token = fields.Char(
        string="Telegram Bot Token",
        config_parameter='auth_telegram.bot_token',
        help="Secret bot token given by @BotFather (e.g. 123456789:AbCdEf...). "
             "It is used to verify the authenticity of Telegram logins.")

    def set_values(self):
        if self.auth_telegram_bot_username:
            self.auth_telegram_bot_username = self.auth_telegram_bot_username.strip().lstrip('@')
        if self.auth_telegram_bot_token:
            self.auth_telegram_bot_token = self.auth_telegram_bot_token.strip()
        return super().set_values()
