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

# (code, section, sequence, Khmer / English label, ledger tax category)
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
    ('VAT06', 'vat', 32,
     "អតប ឥណទានយោងពីខែមុន / VAT Credit Brought Forward", None),
    ('VAT03', 'vat', 33,
     "អតប ត្រូវបង់ / VAT Payable", None),
    ('VAT04', 'vat', 34,
     "អតប ឥណទានយោងទៅមុខ / VAT Credit Carried Forward", None),
    ('VAT05', 'vat', 35,
     "អតប កាតព្វកិច្ចបញ្ច្រាស / VAT Reverse Charge (e-Commerce)",
     'vat_reverse'),
    ('TOS01', 'salary', 40,
     "ពន្ធលើប្រាក់បៀវត្ស / Tax on Salary", 'tos'),
    ('TOS02', 'salary', 41,
     "ពន្ធលើអត្ថប្រយោជន៍បន្ថែម ២០% / Fringe Benefit Tax 20%", 'fbt'),
    ('OTH01', 'other', 50,
     "ពន្ធលើការស្នាក់នៅ ២% / Accommodation Tax 2%", 'accommodation'),
    ('OTH02', 'other', 51,
     "ពន្ធបំភ្លឺសាធារណៈ ៣% / Public Lighting Tax 3%", 'plt'),
    ('OTH03', 'other', 52,
     "អាករពិសេស / Specific Tax", 'specific'),
    ('OTH04', 'other', 53,
     "ពន្ធរំដោះលើការបែងចែកភាគលាភ / Advance Tax on Dividend Distribution",
     'atdd'),
    ('OTH05', 'other', 54,
     "ពន្ធផ្សេងទៀត / Other Taxes", 'other'),
]

# Codes that are informative only and must not be added to the total payable.
INFORMATIVE_CODES = ('VAT01', 'VAT02', 'VAT04', 'VAT06')

SECTIONS = [
    ('ptoi', "Prepayment of Tax on Income"),
    ('wht', "Withholding Tax"),
    ('vat', "Value Added Tax"),
    ('salary', "Salary Taxes"),
    ('other', "Other Taxes"),
]


class L10nKhTaxReport(models.Model):
    _name = 'l10n.kh.tax.report'
    _description = "Cambodia Monthly Tax Declaration (GDT)"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, company_id'
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
    ledger_entry_ids = fields.One2many(
        'l10n.kh.tax.ledger', 'report_id', string="Tax Ledger Entries")
    ledger_entry_count = fields.Integer(
        compute='_compute_ledger_entry_count')
    turnover = fields.Monetary(
        string="Monthly Turnover (Taxable)", readonly=True,
        help="Turnover of the period from the GDT Tax Ledger (sales entries: "
             "VAT taxable, zero-rated and non-VAT turnover). Basis of the 1% "
             "Prepayment of Tax on Income.")
    total_tax_amount = fields.Monetary(
        string="Total Tax Payable", readonly=True, tracking=True)
    total_tax_amount_khr = fields.Float(
        string="Total Tax Payable (KHR)", readonly=True, digits=(16, 0))
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

    def _compute_ledger_entry_count(self):
        for report in self:
            report.ledger_entry_count = self.env['l10n.kh.tax.ledger'] \
                .search_count(report._get_ledger_domain())

    # ------------------------------------------------------------------
    # Tax ledger helpers
    # ------------------------------------------------------------------
    def _get_ledger_domain(self):
        """Entries of the period that belong to this declaration: either not
        yet assigned to any declaration, or already assigned to this one."""
        self.ensure_one()
        return [
            ('company_id', '=', self.company_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            '|', ('report_id', '=', False), ('report_id', '=', self.id),
        ]

    def _get_ledger_entries(self, entry_types=None):
        self.ensure_one()
        domain = self._get_ledger_domain()
        if entry_types:
            domain.append(('entry_type', 'in', entry_types))
        return self.env['l10n.kh.tax.ledger'].search(
            domain, order='date, id')

    def _get_registers(self):
        """Registers printed as annexes for the government auditor."""
        self.ensure_one()
        return [
            (_("Sales Register (VAT Output, Zero-rated & Turnover)"),
             self._get_ledger_entries(['sale'])),
            (_("Purchase Register (VAT Input)"),
             self._get_ledger_entries(['purchase'])),
            (_("Withholding Tax Register"),
             self._get_ledger_entries(['wht'])),
            (_("Salary & Other Taxes Register"),
             self._get_ledger_entries(['salary', 'other'])),
        ]

    def action_view_ledger(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("GDT Tax Ledger - %s", self.name),
            'res_model': 'l10n.kh.tax.ledger',
            'view_mode': 'list,form,pivot',
            'domain': self._get_ledger_domain(),
            'context': {
                'default_company_id': self.company_id.id,
                'default_date': self.date_to,
            },
        }

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------
    def _get_previous_vat_credit(self):
        """VAT credit carried forward from the previous month's declaration
        (the excess input VAT offsets the following months' output VAT)."""
        self.ensure_one()
        prev_year, prev_month = (self.year, int(self.month) - 1) \
            if int(self.month) > 1 else (self.year - 1, 12)
        prev_line = self.env['l10n.kh.tax.report.line'].search([
            ('company_id', '=', self.company_id.id),
            ('code', '=', 'VAT04'),
            ('report_id.year', '=', prev_year),
            ('report_id.month', '=', str(prev_month)),
        ], limit=1)
        return prev_line.tax_amount or 0.0

    def action_compute(self):
        for report in self:
            if report.state != 'draft':
                raise UserError(_("Only draft declarations can be recomputed."))
            # Rebuild the tax book of the period from the reportable Odoo
            # documents (manual and locked entries are preserved), then
            # compute the declaration from the tax book only.
            self.env['l10n.kh.tax.ledger']._sync_period(
                report.company_id, report.date_from, report.date_to)
            report.line_ids.unlink()

            amounts = {}
            groups = self.env['l10n.kh.tax.ledger']._read_group(
                report._get_ledger_domain(),
                groupby=['tax_category'],
                aggregates=['base_amount:sum', 'tax_amount:sum'],
            )
            for category, base, tax in groups:
                amounts[category] = (base or 0.0, tax or 0.0)

            turnover = sum(amounts.get(cat, (0.0, 0.0))[0]
                           for cat in ('vat_sale', 'vat_zero', 'turnover'))
            vat_out_base, vat_out = amounts.get('vat_sale', (0.0, 0.0))
            vat_in_base, vat_in = amounts.get('vat_purchase', (0.0, 0.0))
            vat_credit_bf = report._get_previous_vat_credit()
            vat_net = vat_out - vat_in - vat_credit_bf
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
                elif code == 'VAT06':
                    base, amount = 0.0, vat_credit_bf
                elif code == 'VAT03':
                    base, amount = 0.0, vat_payable
                elif code == 'VAT04':
                    base, amount = 0.0, vat_credit
                else:
                    base, amount = amounts.get(category, (0.0, 0.0))
                if code not in INFORMATIVE_CODES:
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
                "Declaration computed from the GDT Tax Ledger: turnover "
                "%(turnover)s, total tax payable %(total)s.",
                turnover=turnover, total=total))
        return True

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_confirm(self):
        for report in self:
            if report.state != 'draft':
                raise UserError(_("Only draft declarations can be confirmed."))
            if not report.line_ids:
                raise UserError(_("Compute the declaration before confirming it."))
            entries = report._get_ledger_entries()
            entries.with_context(l10n_kh_tax_lock=True).write({
                'report_id': report.id,
                'locked': True,
            })
            report.state = 'confirmed'
            report.message_post(body=_(
                "Declaration confirmed: %s tax ledger entries locked for "
                "the government audit trail.", len(entries)))
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
        for report in self:
            report.ledger_entry_ids.with_context(l10n_kh_tax_lock=True).write({
                'locked': False,
                'report_id': False,
            })
            report.write({'state': 'draft', 'filed_date': False,
                          'filed_by_id': False})
        return True

    @api.ondelete(at_uninstall=False)
    def _unlink_except_confirmed(self):
        if any(report.state != 'draft' for report in self):
            raise UserError(_(
                "Confirmed or filed declarations cannot be deleted: they "
                "lock the tax ledger entries of the government audit trail. "
                "Reset the declaration to draft first."))

    # ------------------------------------------------------------------
    # e-Filing export
    # ------------------------------------------------------------------
    def action_export_efiling(self):
        """Build the GDT e-Filing workbook (sales, purchase and withholding
        registers) from the tax ledger."""
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

        categories = dict(
            self.env['l10n.kh.tax.ledger']._fields['tax_category'].selection)
        sheets = [
            (_("Sales"), ['sale']),
            (_("Purchases"), ['purchase']),
            (_("Withholding Tax"), ['wht']),
            (_("Salary & Other"), ['salary', 'other']),
        ]
        for sheet_name, entry_types in sheets:
            sheet = workbook.add_worksheet(sheet_name)
            headers = [
                _("No."), _("Date"), _("Invoice / Document No."), _("TIN"),
                _("Name"), _("Description"), _("Tax Category"),
                _("Amount Excl. Tax"), _("Tax Amount"), _("Total Amount"),
                _("Total (KHR)"),
            ]
            for col, header in enumerate(headers):
                sheet.write(0, col, header, header_fmt)
            sheet.set_column(0, 0, 5)
            sheet.set_column(1, 6, 20)
            sheet.set_column(7, 10, 16)

            for row, entry in enumerate(
                    self._get_ledger_entries(entry_types), start=1):
                sheet.write(row, 0, row, cell_fmt)
                sheet.write_datetime(row, 1, entry.date, date_fmt)
                sheet.write(row, 2, entry.invoice_number or '', cell_fmt)
                sheet.write(row, 3, entry.partner_tin or '', cell_fmt)
                sheet.write(row, 4, entry.partner_name or '', cell_fmt)
                sheet.write(row, 5, entry.description or '', cell_fmt)
                sheet.write(row, 6, categories.get(entry.tax_category, ''),
                            cell_fmt)
                sheet.write_number(row, 7, entry.base_amount, money_fmt)
                sheet.write_number(row, 8, entry.tax_amount, money_fmt)
                sheet.write_number(row, 9, entry.total_amount, money_fmt)
                sheet.write_number(row, 10,
                                   entry.total_amount * self.exchange_rate,
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
            # Idempotent: also creates the Cambodian taxes for companies
            # added after installation, once their chart of accounts exists.
            company._l10n_kh_create_taxes()
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
    amount_khr = fields.Float(
        string="Tax Amount (KHR)", compute='_compute_amount_khr', store=True,
        digits=(16, 0))

    @api.depends('tax_amount', 'report_id.exchange_rate')
    def _compute_amount_khr(self):
        for line in self:
            line.amount_khr = line.tax_amount * line.report_id.exchange_rate
