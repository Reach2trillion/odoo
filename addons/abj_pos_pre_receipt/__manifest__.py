{
    "name": "ABJ POS Pre-Receipt (Print Bill)",
    "version": "18.0.1.0.0",
    "category": "Sales/Point of Sale",
    "summary": "Print the POS bill before payment without validating or locking the order.",
    "description": """
Adds a "Print Bill" button to the POS product screen.

* Prints the current order through the configured receipt printer
  (falls back to the browser print dialog).
* Does NOT finalize the order, does NOT open the payment/receipt screen,
  so the cashier can keep editing the order, switch orders, or pay later.
* The printed bill is clearly marked "PRE-RECEIPT - NOT PAID" so it cannot
  be mistaken for a proof of payment.

Replaces the third-party module cst_pos_pre_receipt (uninstall it first).
""",
    "author": "ABJ SkinCare",
    "license": "LGPL-3",
    "depends": ["point_of_sale"],
    "assets": {
        "point_of_sale._assets_pos": [
            "abj_pos_pre_receipt/static/src/**/*",
        ],
    },
    "installable": True,
    "application": False,
}
