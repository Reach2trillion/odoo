# Part of the auth_telegram module. License LGPL-3.
{
    'name': 'Telegram Login',
    'version': '18.0.1.0.1',
    'category': 'Authentication',
    'summary': 'Let users sign in or sign up with their Telegram account',
    'description': """
Telegram Authentication
=======================
Adds a "Log in with Telegram" button to the Odoo login page, based on the
official Telegram Login Widget (https://core.telegram.org/widgets/login).

- Existing users linked to a Telegram account can log in with one click.
- Unknown Telegram accounts can be turned into new (portal) users
  automatically when free sign up is enabled in Settings.
- Logged-in users can securely link / unlink their own Telegram account
  at /auth/telegram/link.
""",
    'author': 'Reach2trillion',
    'website': 'https://github.com/Reach2trillion/odoo',
    'depends': ['web', 'auth_signup', 'base_setup'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/res_users_views.xml',
        'views/auth_telegram_templates.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
