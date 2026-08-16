# Part of the telegram_notification module. License LGPL-3.
{
    'name': 'Telegram Notifications',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Notify customers on Telegram: quotations, orders, deliveries, invoices',
    'description': """
Telegram Notifications
======================
Sends Telegram messages to customers whose account is linked with the
Telegram Login module (auth_telegram):

- Quotation marked as sent
- Sales order confirmed
- Delivery shipped (with carrier tracking reference and link)
- Customer invoice posted

Also shows the customer's Telegram username on the contact form so your
team can reach them at t.me/<username>.

Customers receive messages only if they allowed the bot to contact them
(the login button asks for this permission) or pressed Start on the bot.
""",
    'author': 'Reach2trillion',
    'website': 'https://github.com/Reach2trillion/odoo',
    'depends': ['auth_telegram', 'sale_management', 'sale_stock', 'account', 'delivery'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
