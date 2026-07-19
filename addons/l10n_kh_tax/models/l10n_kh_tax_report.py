# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import calendar
import io
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

MONTHS = [
    ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
    ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
    ('9', 'September'), ('10', 'October'), ('11', 'November'),
    ('12', 'December'),
]

# (code, section, sequence, Khmer / English label, tax category or None)
REPORT_LINES = [
    ('PRE01', 'ptoi', 10,
     "ប្រាក់រំដោះពន្ធលើប្រាក់ចំណូល ១% / Prepayment of Tax on Income 1%", None),
    ('WHT01', 'wht', 20,
     "ពន្ធកាត់ទុក ១០% ការជួលអចលនទ្រព្យ / WHT 10% Rental (Resident)", 'wht_rent'),
    ('WHT02', 'wht', 21,
     "ពន្ធកាត់ទុក ១៥% សេវាកម្ម / WHT 15% Services (Resident)", 'wht_service'),
    ('WHT03', 'wht', 22,
     "ពន្ធកាត់ទុក ១៥% សួយសារ / WHT 15% Royalties (Resident)", 'wht_royalty'),
    ('WHT04', 'wht', 23,
     "ពន្ធកាត់ទុក ៦% ការប្រាក់មានកាលកំណត់ / WHT 6% Fixed Deposit Interest",
     'wht_interest_fixed'),
    ('WHT05', 'wht', 24,
     "ពន្ធកាត់ទុក ៤% ការប្រាក់សន្សំ / WHT 4% Saving Interest",
     'wht_interest_saving'),
    ('WHT06', 'wht', 25,
     "ពន្ធកាត់ទុក ១៤% អនិវាសនជន / WHT 14% Non-Resident", 'wht_nonresident'),
    ('VAT01', 'vat', 30,
     "អតប លើការលក់ / VAT Output (Sales 10%)", 'vat_sale'),
    ('VAT02', 'vat', 31,
     "អតប លើការទិញ / VAT Input (Purchases 10%)", 'vat_purchase'),
    ('VAT03', 'vat', 32,
     "អតប ត្រូវបង់ / VAT Payable", None),
    ('VAT04', 'vat', 33,
     "អតប ឥណទានយោងទៅមុខ / VAT Credit Carried Forward", None),
    ('OTH01', 'other', 40,
     "ពន្ធលើការស្នាក់នៅ ២% / Accommodation Tax 2%", 'accommodation'),
    ('OTH02', 'other', 41,
     "ពន្ធបំភ្លឺសាធារណៈ ៣% / Public Lighting Tax 3%", 'plt'),
    ('OTH03', 'other', 42,
     "អាករពិសេស / Specific Tax", 'specific'),
    ('TOS01', 'salary', 50,
     "ពន្ធលើប្រាក់បៀវត្ស / Tax on Salary", None),
]

SECTIONS = [
    ('ptoi', "Prepayment of Tax on Income"),
    ('wht', "Withholding Tax"),
    ('vat', "Value Added Tax"),
    ('other', "Other Taxes"),
    ('salary', "Tax on Salary"),
]


class L10nKhTaxReport(models.Model):
    _name = 'l10n.kh.tax.report'
    _description = "Cambodia Monthly Tax Declaration (GDT)"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'year desc, month desc, company_id'
    _rec_name = 'name'

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', required=True, readonly=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    month = fields.Selection(
        MONTHS, required=True, tracking=True,
        default=lambda self: str(fields.Date.context_today(self).month))
    year = fields.Integer(
        required=True, tracking=True,
        default=lambda self: fields.Date.context_today(self).year)
    date_from = fields.Date(compute='_compute_dates', store=True)
    date_to = fields.Date(compute='_compute_dates', store=True)
    exchange_rate = fields.Float(
        string="KHR Exchange Rate", digits=(12, 2), tracking=True,
        default=lambda self: self.env.company.l10n_kh_exchange_rate or 4100.0,
        help="Official monthly exchange rate (KHR per unit of company "
             "currency) published by the GDT / National Bank of Cambodia.")
    state = fields.Selection(
        [('draft', "Draft"),
         ('confirmed', "Confirmed"),
         ('filed', "Filed (e-Filing)")],
        default='draft', required=True, tracking=True, copy=False)
    line_ids = fields.One2many(
        'l10n.kh.tax.report.line', 'report_id', string="Declaration Lines")
    turnover = fields.Monetary(
        string="Monthly Turnover (Taxable)", readonly=True,
        help="Turnover of the period computed from the income accounts "
             "flagged 'Report to GDT (Cambodia)', excluding entries flagged "
             "'Exclude from Cambodia Tax Report'. Basis of the 1% PToI.")
    total_tax_amount = fields.Monetary(
        string="Total Tax Payable", readonly=True, tracking=True)
    total_tax_amount_khr = fields.Monetary(
        string="Total Tax Payable (KHR)", readonly=True,
        currency_field='currency_id')
    filed_date = fields.Date(readonly=True, copy=False, tracking=True)
    filed_by_id = fields.Many2one(
        'res.users', string="Filed By", readonly=True, copy=False)
    efiling_attachment_id = fields.Many2one(
        'ir.attachment', string="e-Filing Export", readonly=True, copy=False)
    note = fields.Text(string="Notes / Audit Remarks")

    _sql_constraints = [
        ('period_company_uniq', 'unique(company_id, year, month)',
         "A tax declaration already exists for this company and period."),
    ]

    @api.depends('month', 'year', 'company_id')
    def _compute_name(self):
        for report in self:
            month = dict(MONTHS).get(report.month or '', '')
            report.name = _("GDT Monthly Tax Declaration - %(month)s %(year)s",
                            month=month, year=report.year)

    @api.depends('month', 'year')
    def _compute_dates(self):
        for report in self:
            if not report.month or not report.year:
                report.date_from = report.date_to = False
                continue
            month = int(report.month)
            last_day = calendar.monthrange(report.year, month)[1]
            report.date_from = date(report.year, month, 1)
            report.date_to = date(report.year, month, last_day)

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------
    def _get_move_line_domain(self):
        self.ensure_one()
        return [
            ('company_id', '=', self.company_id.id),
            ('parent_state', '=', 'posted'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('move_id.l10n_kh_exclude_tax_report', '=', False),
        ]

    def _compute_turnover(self):
        """Taxable turnover = income posted on GDT-reportable accounts."""
        self.ensure_one()
        groups = self.env['account.move.line']._read_group(
            self._get_move_line_domain() + [
                ('account_id.account_type', 'in', ('income', 'income_other')),
                ('account_id.l10n_kh_tax_reportable', '=', True),
                ('display_type', 'not in', ('line_section', 'line_note')),
            ],
            aggregates=['balance:sum'],
        )
        balance = groups[0][0] if groups else 0.0
        return -(balance or 0.0)

    def _compute_tax_amounts(self):
        """Return {category: (base, tax_amount)} from posted tax lines."""
        self.ensure_one()
        result = {}
        groups = self.env['account.move.line']._read_group(
            self._get_move_line_domain() + [
                ('tax_line_id.l10n_kh_tax_category', '!=', False),
            ],
            groupby=['tax_line_id'],
            aggregates=['balance:sum', 'tax_base_amount:sum'],
        )
        for tax, balance, base in groups:
            category = tax.l10n_kh_tax_category
            base_total, tax_total = result.get(category, (0.0, 0.0))
            # Sales taxes and withholding taxes are posted in credit
            # (negative balance): report them as positive amounts.
            # Purchase VAT is posted in debit (positive balance).
            if category == 'vat_purchase':
                amount = balance or 0.0
            else:
                amount = -(balance or 0.0)
            result[category] = (base_total + abs(base or 0.0),
                                tax_total + amount)
        return result

    def _compute_tax_on_salary(self):
        """Sum Tax on Salary from Cambodian payslips when payroll is installed."""
        self.ensure_one()
        if 'hr.payslip' not in self.env:
            return 0.0
        payslips = self.env['hr.payslip'].search([
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ('done', 'paid')),
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
        ])
        lines = payslips.mapped('line_ids').filtered(
            lambda line: line.code in ('TOS', 'ToS', 'TAX', 'TOSNR'))
        return abs(sum(lines.mapped('total')))

    def action_compute(self):
        for report in self:
            if report.state != 'draft':
                raise UserError(_("Only draft declarations can be recomputed."))
            report.line_ids.unlink()

            turnover = report._compute_turnover()
            tax_amounts = report._compute_tax_amounts()
            tos_amount = report._compute_tax_on_salary()

            vat_out_base, vat_out = tax_amounts.get('vat_sale', (0.0, 0.0))
            vat_in_base, vat_in = tax_amounts.get('vat_purchase', (0.0, 0.0))
            vat_net = vat_out - vat_in
            vat_payable = max(vat_net, 0.0)
            vat_credit = max(-vat_net, 0.0)

            lines = []
            total = 0.0
            for code, section, sequence, label, category in REPORT_LINES:
                if code == 'PRE01':
                    base, amount = turnover, turnover * 0.01
                elif code == 'VAT01':
                    base, amount = vat_out_base, vat_out
                elif code == 'VAT02':
                    base, amount = vat_in_base, vat_in
                elif code == 'VAT03':
                    base, amount = 0.0, vat_payable
                elif code == 'VAT04':
                    base, amount = 0.0, vat_credit
                elif code == 'TOS01':
                    base, amount = 0.0, tos_amount
                else:
                    base, amount = tax_amounts.get(category, (0.0, 0.0))
                # VAT01/VAT02/VAT04 are informative; VAT03 carries the payable.
                if code not in ('VAT01', 'VAT02', 'VAT04'):
                    total += amount
                lines.append((0, 0, {
                    'code': code,
                    'section': section,
                    'sequence': sequence,
                    'name': label,
                    'base_amount': base,
                    'tax_amount': amount,
                }))

            report.write({
                'line_ids': lines,
                'turnover': turnover,
                'total_tax_amount': total,
                'total_tax_amount_khr': total * report.exchange_rate,
            })
            report.message_post(body=_(
                "Declaration computed: turnover %(turnover)s, "
                "total tax payable %(total)s.",
                turnover=turnover, total=total))
        return True

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_confirm(self):
        for report in self:
            if not report.line_ids:
                raise UserError(_("Compute the declaration before confirming it."))
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
                "Declaration filed on the GDT e-Filing portal by %s.",
                self.env.user.name))
        return True

    def action_reset_to_draft(self):
        self.write({'state': 'draft', 'filed_date': False,
                    'filed_by_id': False})
        return True

    # ------------------------------------------------------------------
    # e-Filing export
    # ------------------------------------------------------------------
    def _get_efiling_moves(self, move_types):
        self.ensure_one()
        return self.env['account.move'].search([
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'posted'),
            ('move_type', 'in', move_types),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('l10n_kh_exclude_tax_report', '=', False),
        ], order='date, name')

    def action_export_efiling(self):
        """Build the GDT e-Filing workbook (sales & purchase transaction lists)."""
        self.ensure_one()
        try:
            import xlsxwriter
        except ImportError as error:  # pragma: no cover
            raise UserError(_("The Python library 'xlsxwriter' is required "
                              "for the e-Filing export.")) from error

        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        header_fmt = workbook.add_format(
            {'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
        money_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        cell_fmt = workbook.add_format({'border': 1})
        date_fmt = workbook.add_format(
            {'num_format': 'dd-mm-yyyy', 'border': 1})

        sheets = [
            (_("Sales"), ('out_invoice', 'out_refund'),
             _("Customer TIN"), _("Customer Name")),
            (_("Purchases"), ('in_invoice', 'in_refund'),
             _("Supplier TIN"), _("Supplier Name")),
        ]
        for sheet_name, move_types, tin_label, name_label in sheets:
            sheet = workbook.add_worksheet(sheet_name)
            headers = [
                _("No."), _("Date"), _("Invoice No."), tin_label, name_label,
                _("Description"), _("Amount Excl. Tax"), _("VAT Amount"),
                _("Total Amount"), _("Total (KHR)"),
            ]
            for col, header in enumerate(headers):
                sheet.write(0, col, header, header_fmt)
            sheet.set_column(0, 0, 5)
            sheet.set_column(1, 5, 18)
            sheet.set_column(6, 9, 16)

            for row, move in enumerate(self._get_efiling_moves(move_types),
                                       start=1):
                sign = -1 if move.move_type in ('out_refund', 'in_refund') else 1
                untaxed = sign * move.amount_untaxed
                total = sign * move.amount_total
                vat = total - untaxed
                sheet.write(row, 0, row, cell_fmt)
                sheet.write_datetime(row, 1, move.date, date_fmt)
                sheet.write(row, 2, move.name or '', cell_fmt)
                sheet.write(row, 3, move.partner_id.vat or '', cell_fmt)
                sheet.write(row, 4, move.partner_id.name or '', cell_fmt)
                sheet.write(row, 5, move.ref or move.invoice_origin or '',
                            cell_fmt)
                sheet.write_number(row, 6, untaxed, money_fmt)
                sheet.write_number(row, 7, vat, money_fmt)
                sheet.write_number(row, 8, total, money_fmt)
                sheet.write_number(row, 9, total * self.exchange_rate,
                                   money_fmt)
        workbook.close()

        filename = "GDT_eFiling_%s_%02d_%s.xlsx" % (
            self.year, int(self.month),
            (self.company_id.l10n_kh_tin or self.company_id.name or ''
             ).replace(' ', '_'))
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(buffer.getvalue()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.'
                        'spreadsheetml.sheet',
        })
        self.efiling_attachment_id = attachment
        self.message_post(
            body=_("e-Filing export generated."),
            attachment_ids=attachment.ids)
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    # ------------------------------------------------------------------
    # Scheduled action
    # ------------------------------------------------------------------
    @api.model
    def _cron_generate_monthly(self):
        """Create and compute the declaration of the previous month for every
        Cambodian company. Runs daily and is idempotent, so the declaration
        appears on the 1st day of each month."""
        today = fields.Date.context_today(self)
        year, month = (today.year, today.month - 1) if today.month > 1 \
            else (today.year - 1, 12)
        companies = self.env['res.company'].search([])
        for company in companies:
            if not company._l10n_kh_is_cambodian():
                continue
            existing = self.search([
                ('company_id', '=', company.id),
                ('year', '=', year),
                ('month', '=', str(month)),
            ], limit=1)
            if existing:
                continue
            report = self.with_company(company).create({
                'company_id': company.id,
                'year': year,
                'month': str(month),
                'exchange_rate': company.l10n_kh_exchange_rate or 4100.0,
            })
            report.action_compute()
            report.message_post(body=_(
                "Declaration generated automatically by the monthly "
                "scheduled action. Please review it, confirm it and file it "
                "on the GDT e-Filing portal before the 25th."))


class L10nKhTaxReportLine(models.Model):
    _name = 'l10n.kh.tax.report.line'
    _description = "Cambodia Monthly Tax Declaration Line"
    _order = 'sequence, id'

    report_id = fields.Many2one(
        'l10n.kh.tax.report', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='report_id.company_id', store=True)
    currency_id = fields.Many2one(related='report_id.currency_id')
    sequence = fields.Integer(default=10)
    section = fields.Selection(SECTIONS, required=True, default='other')
    code = fields.Char(required=True)
    name = fields.Char(string="Description", required=True)
    base_amount = fields.Monetary(string="Tax Base")
    tax_amount = fields.Monetary(string="Tax Amount")
    amount_khr = fields.Monetary(
        string="Tax Amount (KHR)", compute='_compute_amount_khr', store=True)

    @api.depends('tax_amount', 'report_id.exchange_rate')
    def _compute_amount_khr(self):
        for line in self:
            line.amount_khr = line.tax_amount * line.report_id.exchange_rate
