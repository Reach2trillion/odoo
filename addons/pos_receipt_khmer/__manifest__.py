{
    'name': 'POS Khmer Bilingual Receipt (ABJ)',
    'version': '18.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Khmer / English customer receipt and cash in/out slip for the Point of Sale, '
               'with the KHR total, exchange rate and riel change.',
    'description': """
Bilingual Khmer / English POS receipt
=====================================
* Letterhead with the Khmer and English shop name, address, phone, web, e-mail and TIN.
* Document title band (វិក្កយបត្រ / INVOICE or បង្កាន់ដៃលក់ / SALES RECEIPT), number, date
  (Asia/Phnom_Penh), cashier and customer.
* USD total with the exact KHR total, the exchange rate, and change in USD and riel
  (cash change rounded to 100 riel with an explicit rounding row).
* Unpaid pre-receipts are clearly marked NOT PAID / AMOUNT DUE and never print a negative change.
* Bilingual cash in / cash out slip.
* Bundled Khmer font (Kantumruy Pro, SIL OFL 1.1) so the receipt prints the same on every device.

See README.md for settings and notes.
""",
    'author': 'ABJ SkinCare',
    'depends': ['point_of_sale', 'pos_hr', 'pos_loyalty', 'pos_sale'],
    'data': [
        'views/res_company_views.xml',
        'views/pos_payment_method_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_receipt_khmer/static/src/**/*',
        ],
        'web.assets_tests': [
            'pos_receipt_khmer/static/tests/tours/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
