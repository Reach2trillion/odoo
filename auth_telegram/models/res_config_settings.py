# Part of the auth_telegram module. License LGPL-3.
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    auth_telegram_login_mode = fields.Selection([
        ('bot', "Telegram chat: customer taps Start in the bot and confirms (recommended)"),
        ('oidc', "OpenID Connect (Telegram authorization page)"),
        ('widget', "Legacy Login Widget (deprecated by Telegram)"),
    ], string="Telegram Login Method", config_parameter='auth_telegram.login_mode')
    auth_telegram_bot_username = fields.Char(
        string="Telegram Bot Username",
        config_parameter='auth_telegram.bot_username',
        help="Username of your Telegram bot, without the leading @ (e.g. my_company_bot).")
    auth_telegram_bot_token = fields.Char(
        string="Telegram Bot Token",
        config_parameter='auth_telegram.bot_token',
        help="Secret bot token given by @BotFather (e.g. 123456789:AbCdEf...). "
             "Used for the chat login, notifications, and the legacy widget.")
    auth_telegram_client_id = fields.Char(
        string="Telegram Client ID",
        config_parameter='auth_telegram.client_id',
        help="Client ID from @BotFather's OpenID Connect Login settings "
             "(usually the numeric bot ID). Only for the OpenID Connect method.")
    auth_telegram_client_secret = fields.Char(
        string="Telegram Client Secret",
        config_parameter='auth_telegram.client_secret',
        help="Client Secret from @BotFather's OpenID Connect Login settings.")
    auth_telegram_bot_request_phone = fields.Boolean(
        string="Ask for phone number after login", default=True,
        help="After a successful chat login, the bot asks the customer to share "
             "their phone number with one tap (only when the contact has none).")
    auth_telegram_bot_match_code = fields.Boolean(
        string="One-time code (recommended)",
        help="After the customer taps Yes in Telegram, the bot sends them a one-time "
             "code that they type on the website to finish. This prevents accidental "
             "approvals and makes it much harder to trick a customer with somebody "
             "else's login link: the attacker would also need the code, which the bot "
             "tells the customer never to share. A customer who nevertheless passes "
             "the code on to a third party can still be tricked.")
    auth_telegram_webhook_url = fields.Char(compute='_compute_auth_telegram_webhook')
    auth_telegram_webhook_status = fields.Char(compute='_compute_auth_telegram_webhook')
    auth_telegram_webhook_ok = fields.Boolean(compute='_compute_auth_telegram_webhook')

    def _compute_auth_telegram_webhook(self):
        Bot = self.env['telegram.bot']
        ICP = self.env['ir.config_parameter'].sudo()
        status = ICP.get_param('auth_telegram.webhook_status', "Not registered")
        ok = Bot._webhook_registered()
        for settings in self:
            settings.auth_telegram_webhook_url = Bot._webhook_url()
            settings.auth_telegram_webhook_status = status
            settings.auth_telegram_webhook_ok = ok

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        res['auth_telegram_bot_request_phone'] = ICP.get_param('auth_telegram.bot_request_phone', '1') != '0'
        res['auth_telegram_bot_match_code'] = ICP.get_param('auth_telegram.bot_match_code') == '1'
        # config_parameter fields are read by default_get() *before* it merges
        # get_values(), and base get_values() returns {}: the stored method is
        # never in `res` here, so look at the parameter itself. Only propose a
        # method when none was ever chosen (fresh install); a stored value
        # (migration or administrator's choice) must not be overridden, or an
        # unrelated settings save would silently switch the login method.
        if not ICP.get_param('auth_telegram.login_mode'):
            has_oidc = ICP.get_param('auth_telegram.client_id') and ICP.get_param('auth_telegram.client_secret')
            res['auth_telegram_login_mode'] = 'oidc' if has_oidc else 'bot'
        return res

    def set_values(self):
        for field in ('auth_telegram_client_id', 'auth_telegram_client_secret',
                      'auth_telegram_bot_username', 'auth_telegram_bot_token'):
            if self[field]:
                self[field] = self[field].strip().lstrip('@') \
                    if field == 'auth_telegram_bot_username' else self[field].strip()
        ICP = self.env['ir.config_parameter'].sudo()
        previous_token = ICP.get_param('auth_telegram.bot_token')
        super().set_values()
        # stored as explicit '1'/'0': an unchecked boolean config_parameter is
        # deleted, which would be indistinguishable from "never configured"
        ICP.set_param('auth_telegram.bot_request_phone', '1' if self.auth_telegram_bot_request_phone else '0')
        ICP.set_param('auth_telegram.bot_match_code', '1' if self.auth_telegram_bot_match_code else '0')
        # chat login needs the webhook: register it automatically when the
        # method is selected and the webhook is not registered on this
        # server's URL, or the token changed
        if self.auth_telegram_login_mode == 'bot' and self.auth_telegram_bot_token:
            Bot = self.env['telegram.bot']
            if previous_token != self.auth_telegram_bot_token or not Bot._webhook_registered():
                Bot._set_webhook()

    def action_auth_telegram_register_webhook(self):
        self.set_values()
        self.env['telegram.bot']._set_webhook()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_auth_telegram_check_webhook(self):
        self.env['telegram.bot']._check_webhook()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_auth_telegram_remove_webhook(self):
        self.env['telegram.bot']._delete_webhook()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
