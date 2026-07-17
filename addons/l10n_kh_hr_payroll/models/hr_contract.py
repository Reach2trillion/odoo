from odoo import fields, models


class HrContract(models.Model):
    _inherit = 'hr.contract'

    l10n_kh_contract_duration = fields.Selection(
        selection=[
            ('udc', "Unlimited Duration Contract (UDC)"),
            ('fdc', "Fixed Duration Contract (FDC)"),
        ],
        string="Contract Duration Type (KH)",
        default='udc',
        help="Cambodian Labor Law contract type: Fixed Duration Contract "
             "(maximum 2 years, renewable) or Unlimited Duration Contract.")
    l10n_kh_workplace = fields.Char(
        string="Workplace (ទីកន្លែងធ្វើការ)",
        help="Workplace stated on the printed employment contract. Leave "
             "empty to use the company address.")

    # Monthly allowances (in the contract currency), included in the taxable
    # gross except the non-taxable allowance.
    l10n_kh_housing_allowance = fields.Monetary(
        string="Housing Allowance", tracking=True,
        help="Monthly housing allowance (taxable).")
    l10n_kh_transport_allowance = fields.Monetary(
        string="Transportation Allowance", tracking=True,
        help="Monthly transportation allowance (taxable).")
    l10n_kh_meal_allowance = fields.Monetary(
        string="Meal Allowance", tracking=True,
        help="Monthly meal allowance (taxable).")
    l10n_kh_phone_allowance = fields.Monetary(
        string="Phone Allowance", tracking=True,
        help="Monthly phone/communication allowance (taxable).")
    l10n_kh_other_allowance = fields.Monetary(
        string="Other Taxable Allowance", tracking=True,
        help="Any other recurring monthly allowance subject to Tax on Salary.")
    l10n_kh_nontaxable_allowance = fields.Monetary(
        string="Non-Taxable Allowance", tracking=True,
        help="Recurring monthly benefit exempted from Tax on Salary under "
             "Cambodian regulations (e.g. exempt travel or uniform "
             "allowances within the legal limits). Added to the net payment "
             "after tax.")
