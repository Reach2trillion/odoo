{
    'name': 'Auto Print Shipping Label (80x100 mm) on Delivery Validation',
    'summary': 'Automatically print an 80x100 mm shipping label when a delivery order is validated',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Inventory',
    'author': 'ABJ',
    'license': 'LGPL-3',
    'depends': ['stock'],
    'data': [
        'report/paperformat.xml',
        'report/report_shipping_label.xml',
        'views/stock_picking_type_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'stock_auto_print_label/static/src/js/browser_print_report_handler.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
