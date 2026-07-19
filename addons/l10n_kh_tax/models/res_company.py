# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models

# (category, name, type_tax_use, amount, description on invoice)
KH_TAXES = [
    ('vat_sale', "VAT 10% (Sales)", 'sale', 10.0, "VAT 10%"),
    ('vat_zero', "VAT 0% (Export / Zero-rated)", 'sale', 0.0, "VAT 0%"),
    ('vat_purchase', "VAT 10% (Purchases)", 'purchase', 10.0, "VAT 10%"),
    ('wht_rent', "WHT 10% Rental (Resident)", 'purchase', -10.0, "WHT 10%"),
    ('wht_service', "WHT 15% Services (Resident)", 'purchase', -15.0, "WHT 15%"),
    ('wht_royalty', "WHT 15% Royalties (Resident)", 'purchase', -15.0, "WHT 15%"),
    ('wht_interest_fixed', "WHT 6% Fixed Deposit Interest", 'purchase', -6.0, "WHT 6%"),
    ('wht_interest_saving', "WHT 4% Saving Interest", 'purchase', -4.0, "WHT 4%"),
    ('wht_nonresident', "WHT 14% Non-Resident", 'purchase', -14.0, "WHT 14%"),
    ('accommodation', "Accommodation Tax 2%", 'sale', 2.0, "AT 2%"),
    ('plt', "Public Lighting Tax 3%", 'sale', 3.0, "PLT 3%"),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_kh_tin = fields.Char(
        string="TIN (GDT)",
        help="Tax Identification Number issued by the General Department of "
             "Taxation, used on the monthly declaration and e-Filing export.",
    )
    l10n_kh_taxpayer_type = fields.Selection(
        selection=[
            ('small', "Small Taxpayer"),
            ('medium', "Medium Taxpayer"),
            ('large', "Large Taxpayer"),
        ],
        string="Taxpayer Classification",
        default='medium',
    )
    l10n_kh_gdt_branch = fields.Char(
        string="GDT Tax Branch",
        help="Tax branch / khan-district tax office where the company is "
             "registered.",
    )
    l10n_kh_efiling_account = fields.Char(
        string="e-Filing Account",
        help="Login/account name used on the GDT e-Filing portal "
             "(for reference only, no password is stored).",
    )
    l10n_kh_exchange_rate = fields.Float(
        string="Default KHR Exchange Rate",
        digits=(12, 2),
        default=4100.0,
        help="Default official exchange rate (KHR per unit of company "
             "currency) proposed on new monthly declarations. It can be "
             "adjusted on each declaration with the official monthly rate "
             "published by the GDT / National Bank of Cambodia.",
    )

    def _l10n_kh_is_cambodian(self):
        self.ensure_one()
        return self.country_id.code == 'KH' or not self.country_id

    def _l10n_kh_create_taxes(self):
        """Create the standard Cambodian taxes for the companies (idempotent)."""
        Tax = self.env['account.tax'].sudo()
        for company in self:
            if not company._l10n_kh_is_cambodian():
                continue
            for category, name, tax_use, amount, description in KH_TAXES:
                existing = Tax.with_company(company).search([
                    ('l10n_kh_tax_category', '=', category),
                    ('type_tax_use', '=', tax_use),
                    ('company_id', '=', company.id),
                ], limit=1)
                if existing:
                    continue
                Tax.with_company(company).create({
                    'name': name,
                    'amount_type': 'percent',
                    'amount': amount,
                    'type_tax_use': tax_use,
                    'description': description,
                    'l10n_kh_tax_category': category,
                    'company_id': company.id,
                })

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        companies._l10n_kh_create_taxes()
        return companies
