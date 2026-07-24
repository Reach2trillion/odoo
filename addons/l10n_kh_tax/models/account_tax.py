# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    l10n_kh_tax_category = fields.Selection(
        selection=[
            ('vat_sale', "VAT 10% - Output (Sales)"),
            ('vat_zero', "VAT 0% - Zero-rated (Export)"),
            ('vat_purchase', "VAT 10% - Input (Purchases)"),
            ('wht_rent', "WHT 10% - Rental (Resident)"),
            ('wht_service', "WHT 15% - Services (Resident)"),
            ('wht_royalty', "WHT 15% - Royalties (Resident)"),
            ('wht_interest_fixed', "WHT 6% - Fixed Term Deposit Interest"),
            ('wht_interest_saving', "WHT 4% - Saving Account Interest"),
            ('wht_nonresident', "WHT 14% - Non-Resident"),
            ('vat_reverse', "VAT 10% - Reverse Charge (e-Commerce)"),
            ('tos', "Tax on Salary"),
            ('fbt', "Fringe Benefit Tax 20%"),
            ('accommodation', "Accommodation Tax 2%"),
            ('plt', "Public Lighting Tax 3%"),
            ('specific', "Specific Tax on Certain Merchandise & Services"),
            ('atdd', "Advance Tax on Dividend Distribution"),
            ('other', "Other Cambodian Tax"),
        ],
        string="Cambodia Tax Category",
        help="Maps this tax to a line of the GDT Monthly Tax Declaration. "
             "Taxes without a category are not reported.",
    )
