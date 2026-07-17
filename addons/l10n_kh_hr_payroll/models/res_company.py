from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_kh_tos_exchange_rate = fields.Float(
        string="ToS Exchange Rate (KHR per currency unit)",
        digits=(12, 2),
        default=4100.0,
        help="Exchange rate used to convert payslip amounts into Khmer Riel "
             "for the Tax on Salary and NSSF computations (the General "
             "Department of Taxation publishes the official monthly rate). "
             "With a USD company currency, this is the KHR/USD rate "
             "(e.g. 4100). Set it to 1 if the company currency is KHR.")
