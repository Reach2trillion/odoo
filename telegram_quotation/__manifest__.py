# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Send Quotations via Telegram",
    'summary': "Send sale order quotations to customers through Telegram",
    'description': """
Send Sale Order Quotations via Telegram
========================================
Adds a "Send via Telegram" action on quotations that delivers the
quotation PDF and an itemized message (products, unit price, total)
to the customer's configured Telegram group/chat.

Configuration
-------------
* Set the customer's Telegram Group ID on their contact form
  (Sales & Purchase tab).
* Set the bot token as the system parameter
  ``telegram_quotation.bot_token``
  (Settings > Technical > Parameters > System Parameters).
""",
    'category': 'Sales/Sales',
    'version': '1.0',
    'depends': ['sale'],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'wizard/telegram_message_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
