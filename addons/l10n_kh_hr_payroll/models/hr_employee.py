from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_kh_khmer_name = fields.Char(
        string="Name in Khmer (ឈ្មោះជាអក្សរខ្មែរ)",
        groups="hr.group_hr_user",
        help="Employee full name written in Khmer script, printed on the "
             "payslip and the employment contract.")
    l10n_kh_nssf_id = fields.Char(
        string="NSSF ID (លេខ ប.ស.ស.)",
        groups="hr.group_hr_user",
        help="National Social Security Fund member number.")
    l10n_kh_tax_resident = fields.Selection(
        selection=[
            ('resident', "Resident"),
            ('non_resident', "Non-Resident"),
        ],
        string="Tax Residency (KH)",
        default='resident',
        groups="hr.group_hr_user",
        help="Residents are taxed with the progressive Tax on Salary "
             "brackets. Non-residents are taxed at a flat rate (20%).")
    l10n_kh_tax_dependents = fields.Integer(
        string="Tax Dependents (KH)",
        groups="hr.group_hr_user",
        help="Number of dependents for Tax on Salary: minor children and a "
             "non-working spouse. Each dependent reduces the monthly taxable "
             "base (KHR 150,000 per dependent by default).")
