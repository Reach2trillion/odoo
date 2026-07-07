# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Shipping Label (80x100mm)",
    'version': '18.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': "Print an 80mm x 100mm shipping label for delivery orders",
    'description': """
Shipping Label
==============
Adds a "Shipping Label" print report to delivery orders (Inventory >
Transfers), sized for an 80mm x 100mm thermal label printer.

* Header: company logo, name, website, phone
* Body: customer name, phone, and delivery address

Available from the Print menu on any outgoing delivery.
""",
    'author': 'MRDIL ODOO',
    'license': 'LGPL-3',
    'depends': ['stock'],
    'data': [
        'report/shipping_label_paperformat.xml',
        'report/shipping_label_templates.xml',
        'report/shipping_label_actions.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
