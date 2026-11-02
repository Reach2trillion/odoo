# Part of the auth_telegram module. License LGPL-3.
{
    'name': 'Telegram Login',
    'version': '18.0.3.2.3',
    'category': 'Authentication',
    'summary': 'Let users sign in or sign up with their Telegram account',
    'description': """
Telegram Authentication
=======================
Adds a "Log in with Telegram" button to the Odoo login page.

- Chat login: the customer taps Start in your bot, confirms, and is signed
  in (no OAuth screens); optionally they type a one-time code shown by the
  bot. The bot can then message them and ask for their phone number with
  one tap. OpenID Connect is also supported.
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
        'security/ir.model.access.csv',
        'data/auth_telegram_data.xml',
        'views/res_config_settings_views.xml',
        'views/res_users_views.xml',
        'views/auth_telegram_templates.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
