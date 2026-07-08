# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Delivery Packing Telegram Notification",
    'version': '18.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': "Notify a Telegram group with the products to pack the moment a sale order is confirmed, routed per delivery operation type",
    'description': """
Delivery Packing Telegram Notification
=======================================
The instant a sale order is confirmed, this module sends a Telegram message
to your warehouse team listing exactly what needs to be packed for the
resulting delivery - order reference, customer, and each product with its
quantity.

Custom by operation type (per delivery)
----------------------------------------
Each Delivery operation type (Inventory > Configuration > Operation Types)
gets its own "Telegram Group ID" field, so notifications for "Delivery
Orders - Warehouse 1" can go to one group/chat and "Delivery Orders -
Warehouse 2" to another. Operation types without their own group fall back
to the default group configured in Settings > Inventory.

Requires the "Send by Telegram" module for the bot token configuration
(Settings > General Settings > Send by Telegram).
""",
    'author': 'MRDIL ODOO',
    'license': 'LGPL-3',
    'depends': ['sale', 'stock', 'send_by_telegram'],
    'data': [
        'views/stock_picking_type_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
