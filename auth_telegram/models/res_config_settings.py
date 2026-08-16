# Part of the auth_telegram module. License LGPL-3.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    auth_telegram_client_id = fields.Char(
        string="Telegram Client ID",
        config_parameter='auth_telegram.client_id',
        help="Client ID from @BotFather's OpenID Connect Login settings "
             "(usually the numeric bot ID).")
    auth_telegram_client_secret = fields.Char(
        string="Telegram Client Secret",
        config_parameter='auth_telegram.client_secret',
        help="Client Secret from @BotFather's OpenID Connect Login settings.")
    auth_telegram_bot_username = fields.Char(
        string="Telegram Bot Username",
        config_parameter='auth_telegram.bot_username',
        help="Username of your Telegram bot, without the leading @ (e.g. my_company_bot).")
    auth_telegram_bot_token = fields.Char(
        string="Telegram Bot Token",
        config_parameter='auth_telegram.bot_token',
        help="Secret bot token given by @BotFather (e.g. 123456789:AbCdEf...). "
             "Used to send Telegram notifications, and to verify logins of "
             "bots still using the legacy Login Widget.")

    def set_values(self):
        for field in ('auth_telegram_client_id', 'auth_telegram_client_secret',
                      'auth_telegram_bot_username', 'auth_telegram_bot_token'):
            if self[field]:
                self[field] = self[field].strip().lstrip('@') \
                    if field == 'auth_telegram_bot_username' else self[field].strip()
        return super().set_values()
