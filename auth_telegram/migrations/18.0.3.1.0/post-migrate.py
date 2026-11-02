# Part of the auth_telegram module. License LGPL-3.
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """ Versions before 3.0 had no "Login Method" setting: OpenID Connect was
        used when a Client ID/Secret was set, the legacy widget otherwise.
        Keep that behaviour explicit so the upgrade does not change how
        customers log in; the chat login is opted into from Settings. """
    env = api.Environment(cr, SUPERUSER_ID, {})
    ICP = env['ir.config_parameter'].sudo()
    if ICP.get_param('auth_telegram.login_mode'):
        return
    if ICP.get_param('auth_telegram.client_id') and ICP.get_param('auth_telegram.client_secret'):
        ICP.set_param('auth_telegram.login_mode', 'oidc')
    elif ICP.get_param('auth_telegram.bot_token') and ICP.get_param('auth_telegram.bot_username'):
        ICP.set_param('auth_telegram.login_mode', 'widget')
