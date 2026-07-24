# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Annual Patent Tax by taxpayer classification (KHR).
PATENT_TAX_KHR = {
    'small': 400000.0,
    'medium': 1200000.0,
    'large': 3000000.0,
}


class L10nKhAnnualTaxReport(models.Model):
    """Annual Tax on Income (ToI) declaration for the GDT.

    Computed from the GDT Tax Ledger (not from the Odoo accounting), it
    compares the 20% Tax on Income with the 1% Minimum Tax and credits the
    monthly 1% prepayments already declared."""
    _name = 'l10n.kh.annual.tax.report'
    _description = "Cambodia Annual Tax on Income Declaration (GDT)"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'year desc, company_id'
    _rec_name = 'name'

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', required=True, readonly=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    year = fields.Integer(
        required=True, tracking=True,
        default=lambda self: fields.Date.context_today(self).year - 1)
    date_from = fields.Date(compute='_compute_dates', store=True)
    date_to = fields.Date(compute='_compute_dates', store=True)
    exchange_rate = fields.Float(
        string="KHR Exchange Rate", digits=(12, 2), tracking=True,
        default=lambda self: self.env.company.l10n_kh_exchange_rate or 4100.0)
    state = fields.Selection(
        [('draft', "Draft"),
         ('confirmed', "Confirmed"),
         ('filed', "Filed (e-Filing)")],
        default='draft', required=True, tracking=True, copy=False)

    revenue = fields.Monetary(
        string="Annual Turnover", readonly=True,
        help="Annual turnover from the GDT Tax Ledger sales entries "
             "(VAT taxable, zero-rated and non-VAT turnover). Basis of the "
             "1% Minimum Tax.")
    other_income = fields.Monetary(
        string="Other Taxable Income",
        help="Other income to add to the taxable result (capital gains, "
             "interest, adjustments per the tax return).")
    deductible_expenses = fields.Monetary(
        string="Deductible Expenses",
        help="Total expenses deductible under the Law on Taxation "
             "(after non-deductible add-backs).")
    taxable_income = fields.Monetary(
        compute='_compute_taxes', store=True)
    toi_amount = fields.Monetary(
        string="Tax on Income 20%", compute='_compute_taxes', store=True)
    minimum_tax = fields.Monetary(
        string="Minimum Tax 1%", compute='_compute_taxes', store=True)
    minimum_tax_exempt = fields.Boolean(
        string="Exempt from Minimum Tax",
        help="Enterprises maintaining proper accounting records certified "
             "by the GDT can be exempted from the 1% Minimum Tax.")
    prepaid_toi = fields.Monetary(
        string="Monthly PToI Prepayments", readonly=True,
        help="Sum of the 1% monthly Prepayment of Tax on Income declared on "
             "the monthly declarations of the year.")
    tax_due = fields.Monetary(
        string="Annual Tax Due", compute='_compute_taxes', store=True,
        help="The higher of the Tax on Income 20% and the Minimum Tax 1% "
             "(unless exempt from Minimum Tax).")
    tax_payable = fields.Monetary(
        string="Balance Payable", compute='_compute_taxes', store=True)
    tax_credit = fields.Monetary(
        string="Credit Carried Forward", compute='_compute_taxes', store=True)
    tax_payable_khr = fields.Float(
        string="Balance Payable (KHR)", compute='_compute_taxes', store=True,
        digits=(16, 0))
    patent_tax_khr = fields.Float(
        string="Annual Patent Tax (KHR)",
        compute='_compute_patent_tax', store=True, readonly=False,
        help="Annual Patent Tax due for the business registration renewal, "
             "based on the taxpayer classification (small 400,000 KHR, "
             "medium 1,200,000 KHR, large 3,000,000 KHR or more).")
    filed_date = fields.Date(readonly=True, copy=False, tracking=True)
    filed_by_id = fields.Many2one(
        'res.users', string="Filed By", readonly=True, copy=False)
    note = fields.Text(string="Notes / Audit Remarks")

    _sql_constraints = [
        ('year_company_uniq', 'unique(company_id, year)',
         "An annual declaration already exists for this company and year."),
    ]

    @api.depends('year', 'company_id')
    def _compute_name(self):
        for report in self:
            report.name = _("Annual Tax on Income Declaration - %s",
                            report.year)

    @api.depends('year')
    def _compute_dates(self):
        for report in self:
            if not report.year:
                report.date_from = report.date_to = False
                continue
            report.date_from = date(report.year, 1, 1)
            report.date_to = date(report.year, 12, 31)

    @api.depends('company_id.l10n_kh_taxpayer_type')
    def _compute_patent_tax(self):
        for report in self:
            if not report.patent_tax_khr:
                report.patent_tax_khr = PATENT_TAX_KHR.get(
                    report.company_id.l10n_kh_taxpayer_type, 1200000.0)

    @api.depends('revenue', 'other_income', 'deductible_expenses',
                 'minimum_tax_exempt', 'prepaid_toi', 'exchange_rate')
    def _compute_taxes(self):
        for report in self:
            income = report.revenue + report.other_income \
                - report.deductible_expenses
            report.taxable_income = income
            report.toi_amount = max(income, 0.0) * 0.20
            report.minimum_tax = (report.revenue + report.other_income) * 0.01
            if report.minimum_tax_exempt:
                report.tax_due = report.toi_amount
            else:
                report.tax_due = max(report.toi_amount, report.minimum_tax)
            report.tax_payable = max(report.tax_due - report.prepaid_toi, 0.0)
            report.tax_credit = max(report.prepaid_toi - report.tax_due, 0.0)
            report.tax_payable_khr = report.tax_payable * report.exchange_rate

    def action_compute(self):
        for report in self:
            if report.state != 'draft':
                raise UserError(_("Only draft declarations can be recomputed."))
            # Rebuild the tax book for the whole year first, so months whose
            # monthly declaration was never computed still contribute their
            # turnover (months locked by a confirmed declaration are kept).
            self.env['l10n.kh.tax.ledger']._sync_period(
                report.company_id, report.date_from, report.date_to)
            groups = self.env['l10n.kh.tax.ledger']._read_group(
                [('company_id', '=', report.company_id.id),
                 ('date', '>=', report.date_from),
                 ('date', '<=', report.date_to),
                 ('tax_category', 'in', ('vat_sale', 'vat_zero', 'turnover'))],
                aggregates=['base_amount:sum'],
            )
            revenue = (groups[0][0] if groups else 0.0) or 0.0
            prepaid_lines = self.env['l10n.kh.tax.report.line'].search([
                ('company_id', '=', report.company_id.id),
                ('code', '=', 'PRE01'),
                ('report_id.year', '=', report.year),
                ('report_id.state', 'in', ('confirmed', 'filed')),
            ])
            report.write({
                'revenue': revenue,
                'prepaid_toi': sum(prepaid_lines.mapped('tax_amount')),
            })
            report.message_post(body=_(
                "Annual declaration computed from the GDT Tax Ledger: "
                "turnover %(revenue)s, prepayments %(prepaid)s.",
                revenue=revenue, prepaid=report.prepaid_toi))
        return True

    def action_confirm(self):
        for report in self:
            if report.state != 'draft':
                raise UserError(_("Only draft declarations can be confirmed."))
            report.state = 'confirmed'
        return True

    def action_mark_filed(self):
        for report in self:
            if report.state != 'confirmed':
                raise UserError(_("Only confirmed declarations can be marked "
                                  "as filed."))
            report.write({
                'state': 'filed',
                'filed_date': fields.Date.context_today(report),
                'filed_by_id': self.env.user.id,
            })
            report.message_post(body=_(
                "Annual declaration filed with the GDT by %s.",
                self.env.user.name))
        return True

    def action_reset_to_draft(self):
        self.write({'state': 'draft', 'filed_date': False,
                    'filed_by_id': False})
        return True

    @api.ondelete(at_uninstall=False)
    def _unlink_except_confirmed(self):
        if any(report.state != 'draft' for report in self):
            raise UserError(_(
                "Confirmed or filed annual declarations cannot be deleted. "
                "Reset the declaration to draft first."))
