# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Auto-Print on Sale Confirmation",
    'version': '18.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': "Auto-open the Quotation PDF and/or Shipping Label for printing the moment a sale order is confirmed",
    'description': """
Auto-Print on Sale Confirmation
================================
When a salesperson clicks "Confirm" on a quotation, this module opens a new
browser tab with a print-ready page and automatically triggers the browser's
print dialog - no need to go hunting through the Print menu.

The page contains, combined into a single PDF:

* The standard Sales Order / Quotation report
* The Shipping Label for any outgoing delivery created by the order
  (auto-detects the "Shipping Label 100x80" report if the sh_receipt_reports
  module is installed, otherwise falls back to the stock_shipping_label
  module if present)

Built for a USB/local receipt or label printer attached to the same PC that
confirms the order - there is no server-side silent printing involved, the
browser's native print dialog is triggered for you to confirm.

Configure under Settings > Sales > Auto-Print:
* Enable/disable auto-print entirely
* Include the Quotation PDF, the Shipping Label, or both
* Pick which Shipping Label report to use, if more than one is installed
""",
    'author': 'MRDIL ODOO',
    'license': 'LGPL-3',
    'depends': ['sale', 'stock'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
