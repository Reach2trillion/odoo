# Part of Odoo. See LICENSE file for full copyright and licensing details.
import calendar
from datetime import date as date_cls, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

LEDGER_CATEGORIES = [
    ('turnover', "Turnover (No VAT)"),
    ('vat_sale', "VAT 10% - Output (Sales)"),
    ('vat_zero', "VAT 0% - Zero-rated (Export)"),
    ('vat_purchase', "VAT 10% - Input (Purchases)"),
    ('vat_reverse', "VAT 10% - Reverse Charge (e-Commerce)"),
    ('wht_rent', "WHT 10% - Rental (Resident)"),
    ('wht_service', "WHT 15% - Services (Resident)"),
    ('wht_royalty', "WHT 15% - Royalties (Resident)"),
    ('wht_interest_fixed', "WHT 6% - Fixed Deposit Interest"),
    ('wht_interest_saving', "WHT 4% - Saving Interest"),
    ('wht_nonresident', "WHT 14% - Non-Resident"),
    ('tos', "Tax on Salary"),
    ('fbt', "Fringe Benefit Tax 20%"),
    ('accommodation', "Accommodation Tax 2%"),
    ('plt', "Public Lighting Tax 3%"),
    ('specific', "Specific Tax"),
    ('atdd', "Advance Tax on Dividend Distribution"),
    ('other', "Other"),
]

ENTRY_TYPE_BY_CATEGORY = {
    'turnover': 'sale',
    'vat_sale': 'sale',
    'vat_zero': 'sale',
    'accommodation': 'sale',
    'plt': 'sale',
    'specific': 'sale',
    'vat_purchase': 'purchase',
    'vat_reverse': 'purchase',
    'wht_rent': 'wht',
    'wht_service': 'wht',
    'wht_royalty': 'wht',
    'wht_interest_fixed': 'wht',
    'wht_interest_saving': 'wht',
    'wht_nonresident': 'wht',
    'tos': 'salary',
    'fbt': 'salary',
    'atdd': 'wht',
    'other': 'other',
}

# Withholding-type entries: the tax is deducted FROM the base, so the
# document total is base - tax, not base + tax.
WITHHELD_ENTRY_TYPES = ('wht', 'salary')


class L10nKhTaxLedger(models.Model):
    """Cambodia GDT Tax Ledger.

    A self-contained tax book, independent from the Odoo general ledger,
    holding only the transactions reported to the General Department of
    Taxation. It is the register the government auditor checks: entries are
    synchronised from the selected (reportable) Odoo documents and can also
    be entered manually, so the tax book never exposes the rest of the Odoo
    accounting.
    """
    _name = 'l10n.kh.tax.ledger'
    _description = "Cambodia GDT Tax Ledger Entry"
    _order = 'date, id'

    name = fields.Char(
        string="Reference", required=True, copy=False, readonly=True,
        default=lambda self: _("New"))
    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    date = fields.Date(required=True, index=True,
                       default=fields.Date.context_today)
    entry_type = fields.Selection(
        [('sale', "Sales"),
         ('purchase', "Purchases"),
         ('wht', "Withholding Tax"),
         ('salary', "Salary Taxes"),
         ('other', "Other Taxes")],
        compute='_compute_entry_type', store=True, index=True)
    tax_category = fields.Selection(
        LEDGER_CATEGORIES, required=True, default='turnover', index=True)
    partner_id = fields.Many2one('res.partner', string="Partner")
    partner_name = fields.Char(
        string="Partner Name",
        compute='_compute_partner_info', store=True, readonly=False)
    partner_tin = fields.Char(
        string="Partner TIN",
        compute='_compute_partner_info', store=True, readonly=False)
    invoice_number = fields.Char(string="Invoice / Document No.")
    description = fields.Char()
    base_amount = fields.Monetary(string="Tax Base")
    tax_amount = fields.Monetary(string="Tax Amount")
    total_amount = fields.Monetary(
        string="Total", compute='_compute_total', store=True)
    source = fields.Selection(
        [('odoo', "Synchronised"), ('manual', "Manual")],
        required=True, default='manual', readonly=True,
        help="Synchronised entries are rebuilt from the reportable Odoo "
             "documents each time the monthly declaration is computed. "
             "Manual entries belong only to the tax book.")
    move_id = fields.Many2one(
        'account.move', string="Source Journal Entry", readonly=True,
        ondelete='set null', index=True,
        groups="l10n_kh_tax.group_l10n_kh_tax_user")
    report_id = fields.Many2one(
        'l10n.kh.tax.report', string="Monthly Declaration",
        readonly=True, copy=False, index=True, ondelete='set null')
    locked = fields.Boolean(readonly=True, copy=False,
                            help="Locked entries belong to a confirmed or "
                                 "filed monthly declaration.")
    note = fields.Char(string="Audit Note")

    @api.depends('tax_category')
    def _compute_entry_type(self):
        for entry in self:
            entry.entry_type = ENTRY_TYPE_BY_CATEGORY.get(
                entry.tax_category, 'other')

    @api.depends('partner_id')
    def _compute_partner_info(self):
        for entry in self:
            if entry.partner_id:
                entry.partner_name = entry.partner_id.name
                entry.partner_tin = entry.partner_id.vat
            else:
                entry.partner_name = entry.partner_name or False
                entry.partner_tin = entry.partner_tin or False

    @api.depends('base_amount', 'tax_amount', 'entry_type')
    def _compute_total(self):
        for entry in self:
            if entry.entry_type in WITHHELD_ENTRY_TYPES:
                entry.total_amount = entry.base_amount - entry.tax_amount
            else:
                entry.total_amount = entry.base_amount + entry.tax_amount

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'l10n.kh.tax.ledger') or _("New")
        return super().create(vals_list)

    def _check_not_locked(self):
        if self.env.context.get('l10n_kh_tax_lock'):
            return
        if any(entry.locked for entry in self):
            raise UserError(_(
                "This tax ledger entry belongs to a confirmed monthly "
                "declaration and can no longer be modified. Reset the "
                "declaration to draft first."))

    def write(self, vals):
        if not self.env.context.get('l10n_kh_tax_lock'):
            self._check_not_locked()
        return super().write(vals)

    def unlink(self):
        self._check_not_locked()
        return super().unlink()

    # ------------------------------------------------------------------
    # Synchronisation from the (selected) Odoo accounting
    # ------------------------------------------------------------------
    @api.model
    def _sync_period(self, company, date_from, date_to):
        """Rebuild the synchronised tax book of the period from the
        reportable Odoo documents.

        Which posted documents are reportable depends on the company's
        Cambodia Tax Reporting Mode: by default ('selected') only documents
        explicitly marked "Report to GDT" enter the tax book; in 'all' mode
        every document is reported unless marked "Do Not Report". Non-VAT
        income is only taken from accounts flagged "Report to GDT
        (Cambodia)". Manual and locked entries are preserved.
        """
        self.with_context(l10n_kh_tax_lock=True).search([
            ('company_id', '=', company.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('source', '=', 'odoo'),
            ('locked', '=', False),
        ]).unlink()

        # Documents already covered by locked entries (a confirmed
        # declaration inside the range) must not be synchronised again.
        locked_entries = self.sudo().search([
            ('company_id', '=', company.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('locked', '=', True),
        ])
        locked_move_ids = set(locked_entries.mapped('move_id').ids)

        # Company reporting mode: by default only documents explicitly
        # marked "Report to GDT" enter the tax book ('selected' mode);
        # in 'all' mode everything is reported except "Do Not Report".
        if company.l10n_kh_tax_report_mode == 'all':
            status_domain = [('l10n_kh_tax_status', '!=', 'exclude')]
        else:
            status_domain = [('l10n_kh_tax_status', '=', 'include')]
        moves = self.env['account.move'].search([
            ('company_id', '=', company.id),
            ('state', '=', 'posted'),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            # Cash-basis transfer entries repeat the invoice's tax lines:
            # skip them to avoid declaring the same tax twice.
            ('tax_cash_basis_origin_move_id', '=', False),
            ('id', 'not in', list(locked_move_ids)),
        ] + status_domain)
        vals_list = []
        for move in moves:
            vals_list += self._prepare_entries_from_move(move)

        # Salary taxes are aggregated per month; skip months whose ToS is
        # already covered by a locked entry (confirmed declaration).
        month_start = date_from.replace(day=1)
        while month_start <= date_to:
            last_day = calendar.monthrange(month_start.year,
                                           month_start.month)[1]
            month_end = date_cls(month_start.year, month_start.month, last_day)
            seg_start = max(month_start, date_from)
            seg_end = min(month_end, date_to)
            locked_tos = any(
                entry.tax_category == 'tos' and entry.source == 'odoo'
                and seg_start <= entry.date <= seg_end
                for entry in locked_entries)
            if not locked_tos:
                vals_list += self._prepare_salary_entries(
                    company, seg_start, seg_end)
            month_start = month_end + timedelta(days=1)

        if vals_list:
            self.with_context(l10n_kh_tax_lock=True).create(vals_list)
        return True

    @api.model
    def _prepare_entries_from_move(self, move):
        currency = move.company_id.currency_id
        common = {
            'company_id': move.company_id.id,
            'date': move.date,
            'partner_id': move.partner_id.id,
            'partner_name': move.partner_id.name or False,
            'partner_tin': move.partner_id.vat or False,
            'invoice_number': move.name,
            'description': move.ref or move.invoice_origin or move.name,
            'source': 'odoo',
            'move_id': move.id,
        }
        vals_list = []

        # 1. Tax lines grouped by tax, then by Cambodia tax category.
        #    The base is counted once per tax (each repartition line of a
        #    tax carries the full base) and signed like the tax amount so
        #    credit notes reduce the declared base.
        by_category = {}

        def add(category, base, tax):
            base_total, tax_total = by_category.get(category, (0.0, 0.0))
            by_category[category] = (base_total + base, tax_total + tax)

        lines_by_tax = {}
        for line in move.line_ids:
            if line.tax_line_id.l10n_kh_tax_category:
                lines_by_tax.setdefault(line.tax_line_id, []).append(line)

        for tax, lines in lines_by_tax.items():
            category = tax.l10n_kh_tax_category
            full_base = abs(lines[0].tax_base_amount)
            if category == 'vat_reverse':
                # Standard reverse-charge configuration (+100% deductible /
                # -100% payable repartition): declare the payable leg as
                # reverse-charge VAT and the deductible leg as input VAT,
                # instead of letting the two legs net to zero.
                payable_lines = [
                    line for line in lines
                    if line.tax_repartition_line_id.factor_percent < 0]
                deductible_lines = [
                    line for line in lines if line not in payable_lines]
                payable = -sum(line.balance for line in payable_lines)
                deductible = sum(line.balance for line in deductible_lines)
                if payable_lines:
                    add('vat_reverse',
                        full_base if payable >= 0 else -full_base, payable)
                if deductible_lines:
                    add('vat_purchase',
                        full_base if deductible >= 0 else -full_base,
                        deductible)
                continue
            if category == 'vat_purchase':
                amount = sum(line.balance for line in lines)
            else:
                amount = -sum(line.balance for line in lines)
            add(category, full_base if amount >= 0 else -full_base, amount)

        for category, (base, tax) in by_category.items():
            if currency.is_zero(base) and currency.is_zero(tax):
                continue
            vals_list.append(dict(common, tax_category=category,
                                  base_amount=base, tax_amount=tax))

        # 2. Zero-rated sales: base lines carrying a 0% VAT tax (no tax
        #    line is generated for a 0% tax).
        zero_base = -sum(
            line.balance for line in move.line_ids
            if any(tax.l10n_kh_tax_category == 'vat_zero'
                   for tax in line.tax_ids))
        if not currency.is_zero(zero_base):
            vals_list.append(dict(common, tax_category='vat_zero',
                                  base_amount=zero_base, tax_amount=0.0))

        # 3. Turnover without VAT: reportable income lines that carry no
        #    Cambodian VAT tax (their VAT-taxed siblings are already counted
        #    through the tax base above).
        def is_untaxed_reportable_income(line):
            return (
                line.account_id.account_type in ('income', 'income_other')
                and line.account_id.l10n_kh_tax_reportable
                and line.display_type not in ('line_section', 'line_note',
                                              'tax')
                and not any(tax.l10n_kh_tax_category in ('vat_sale',
                                                         'vat_zero')
                            for tax in line.tax_ids))

        turnover = -sum(line.balance for line in move.line_ids
                        if is_untaxed_reportable_income(line))
        if not currency.is_zero(turnover):
            vals_list.append(dict(common, tax_category='turnover',
                                  base_amount=turnover, tax_amount=0.0))
        return vals_list

    @api.model
    def _prepare_salary_entries(self, company, date_from, date_to):
        """Aggregate the Tax on Salary withheld on the validated payslips of
        the period (when the Cambodian payroll module is installed)."""
        if 'hr.payslip' not in self.env:
            return []
        # sudo: only aggregated Tax on Salary totals reach the tax book;
        # Tax Officers are not expected to hold payroll access rights.
        payslips = self.env['hr.payslip'].sudo().search([
            ('company_id', '=', company.id),
            ('state', 'in', ('done', 'paid')),
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
        ])
        lines = payslips.mapped('line_ids').filtered(
            lambda line: line.code in ('TOS', 'ToS', 'TOSNR'))
        amount = abs(sum(lines.mapped('total')))
        if not amount:
            return []
        return [{
            'company_id': company.id,
            'date': date_to,
            'description': _("Tax on Salary withheld on payslips "
                             "(%(count)s employees)", count=len(payslips)),
            'tax_category': 'tos',
            'base_amount': abs(sum(payslips.mapped('line_ids').filtered(
                lambda line: line.code in ('GROSS',)).mapped('total'))),
            'tax_amount': amount,
            'source': 'odoo',
        }]
