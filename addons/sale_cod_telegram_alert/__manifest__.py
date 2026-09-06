# -*- coding: utf-8 -*-
{
    'name': 'COD Delivery Alert via Telegram + Shipping Label',
    'summary': 'Tell the delivery driver whether to collect cash: Telegram alert '
               'to the packing group and a COD block on the 80x100mm shipping label',
    'description': """
COD Delivery Alert
==================
Records, on every sales order, how the customer pays at delivery
(Cash on Delivery / Already Paid / Pay Later) and pushes that information
to the people who need it:

* a Telegram message in the delivery/packing group (same group as the
  "Delivery Packing Telegram Notification" module) when the order is
  confirmed and/or the delivery is validated, with the amount to collect;
* a bold COD / PAID / PAY LATER block with the amount and a custom driver
  note on the existing 80x100mm shipping label;
* the payment type, amount to collect and note on the delivery order form
  and list, with filters, so the office can see it at a glance.
""",
    'version': '18.0.1.0.0',
    'category': 'Inventory/Delivery',
    'author': 'Reach2trillion',
    'website': 'https://github.com/reach2trillion/odoo',
    'license': 'LGPL-3',
    'depends': [
        'sale_stock',
        'stock_shipping_label',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'report/shipping_label_cod.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
