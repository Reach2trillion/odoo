# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Cambodia - Accounting & Tax Reporting (គណនេយ្យ និងពន្ធដារ កម្ពុជា)',
    'countries': ['kh'],
    'version': '18.0.2.1.0',
    'category': 'Accounting/Localizations/Reporting',
    'license': 'LGPL-3',
    'author': 'ABJ SkinCare',
    'summary': 'Cambodian monthly tax declaration (GDT), VAT, Withholding Tax, '
               'Prepayment of Tax on Income, e-Filing export',
    'description': """
Cambodia Accounting & Tax Localization
======================================
* **GDT Tax Ledger**: a self-contained tax book, independent from the
  Odoo accounting, holding only the transactions reported to the General
  Department of Taxation. This is the register the government auditor
  checks - the rest of the Odoo accounting is excluded. Entries are
  synchronised from the selected (reportable) documents and manual
  entries can be added directly in the tax book.
* **Government Auditor (GDT)** read-only role: access to the tax book
  and declarations only, no access to the Odoo accounting.
* Cambodian taxes created automatically for Cambodian companies:
  VAT 10% (sales / purchases), VAT 0% (export), and the Withholding
  Taxes required by the Law on Taxation (rent 10%, services 15%,
  royalties 15%, interest 6% / 4%, non-resident 14%).
* Monthly Tax Declaration (GDT monthly return) generated automatically
  every month by a scheduled action, covering:
  - Prepayment of Tax on Income (PToI 1% of monthly turnover)
  - Withholding Taxes (resident & non-resident)
  - VAT (output, input, payable / credit carried forward, reverse charge)
  - Tax on Salary & Fringe Benefit Tax (from Cambodian payroll)
  - Accommodation Tax, Public Lighting Tax, Specific Tax, Advance Tax
    on Dividend Distribution
* **Annual Tax on Income declaration**: 20% ToI vs 1% Minimum Tax,
  credit of the monthly prepayments, Patent Tax by classification.
* Only the accounts you select ("Report to GDT" checkbox on the account)
  feed the tax book; journal entries can also be excluded individually
  ("Exclude from Cambodia Tax Report" on the entry).
* e-Filing export: sales, purchase, withholding and salary registers as
  an Excel workbook following the GDT e-Filing upload template.
* KHR conversion using the monthly official exchange rate.
* Audit-ready workflow (Draft -> Confirmed -> Filed); confirming a
  declaration locks its tax ledger entries for the audit trail.
* Printable bilingual Khmer/English declarations (PDF) with the sales,
  purchase, withholding and salary registers as annexes.
    """,
    'depends': [
        'account',
    ],
    'data': [
        'security/l10n_kh_tax_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'data/l10n_kh_sequence_data.xml',
        'views/account_account_views.xml',
        'views/account_tax_views.xml',
        'views/account_move_views.xml',
        'views/res_company_views.xml',
        'views/l10n_kh_tax_ledger_views.xml',
        'views/l10n_kh_tax_report_views.xml',
        'views/l10n_kh_annual_tax_report_views.xml',
        'views/l10n_kh_tax_menus.xml',
        'report/report_actions.xml',
        'report/report_tax_declaration.xml',
        'report/report_annual_declaration.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
