{
    'name': 'ABA KHQR for Point of Sale',
    'version': '18.0.2.2.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Show a scannable ABA / Bakong KHQR on the POS and confirm '
               'the payment automatically through ABA PayWay.',
    'description': """
ABA KHQR for Point of Sale
==========================
* New POS terminal type "ABA KHQR": the cashier picks it, the customer scans
  a KHQR card on screen with ABA Mobile or any Bakong bank app.
* ABA PayWay mode: dynamic QR from the PayWay QR API, payment confirmed
  automatically (PayWay webhook + status polling), order auto-validates.
* Own-KHQR mode: dynamic KHQR built from your shop's ABA KHQR sticker or
  Bakong ID; the cashier confirms after seeing the money arrive.
* Every QR is logged under Point of Sale > Orders > ABA KHQR Payments.
* Customer display: while the cashier's popup is open, the same KHQR is shown
  full-size on the customer-facing display (second screen), with a bilingual
  Khmer/English status and a "Payment received" screen once paid.
""",
    'author': 'ABJ Skincare',
    'license': 'LGPL-3',
    'depends': ['point_of_sale', 'payment'],
    'data': [
        'security/ir.model.access.csv',
        'security/pos_aba_khqr_security.xml',
        'data/ir_cron.xml',
        'views/pos_payment_method_views.xml',
        'views/pos_aba_khqr_request_views.xml',
    ],
    'assets': {
        # Cashier side (POS UI).
        'point_of_sale._assets_pos': [
            'pos_aba_khqr/static/src/app/**/*',
        ],
        # Customer-facing display (second screen): its own bundle, the POS
        # bundle deliberately excludes point_of_sale/static/src/customer_display.
        'point_of_sale.customer_display_assets': [
            'pos_aba_khqr/static/src/customer_display/**/*',
        ],
    },
    'installable': True,
    'application': False,
}
