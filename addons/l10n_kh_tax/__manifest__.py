# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Cambodia - Accounting & Tax Reporting (គណនេយ្យ និងពន្ធដារ កម្ពុជា)',
    'countries': ['kh'],
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations/Reporting',
    'license': 'LGPL-3',
    'author': 'ABJ SkinCare',
    'summary': 'Cambodian monthly tax declaration (GDT), VAT, Withholding Tax, '
               'Prepayment of Tax on Income, e-Filing export',
    'description': """
Cambodia Accounting & Tax Localization
======================================
* Cambodian taxes created automatically for Cambodian companies:
  VAT 10% (sales / purchases), VAT 0% (export), and the Withholding
  Taxes required by the Law on Taxation (rent 10%, services 15%,
  royalties 15%, interest 6% / 4%, non-resident 14%).
* Monthly Tax Declaration (GDT monthly return) generated automatically
  every month by a scheduled action, covering:
  - Prepayment of Tax on Income (PToI 1% of monthly turnover)
  - Withholding Taxes (resident & non-resident)
  - VAT (output, input, payable or credit carried forward)
  - Tax on Salary (from Cambodian payroll when installed)
* Only the accounts you select ("Report to GDT" checkbox on the account)
  are included in the tax report; journal entries can also be excluded
  individually ("Exclude from Cambodia Tax Report" on the entry).
* e-Filing export: sales and purchase transaction lists as an Excel
  workbook following the GDT e-Filing upload template.
* KHR conversion using the monthly official exchange rate.
* Audit-ready workflow (Draft -> Confirmed -> Filed) with full chatter
  history; filed declarations are locked.
* Printable bilingual Khmer/English monthly declaration (PDF).
    """,
    'depends': [
        'account',
    ],
    'data': [
        'security/l10n_kh_tax_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/account_account_views.xml',
        'views/account_tax_views.xml',
        'views/account_move_views.xml',
        'views/res_company_views.xml',
        'views/l10n_kh_tax_report_views.xml',
        'views/l10n_kh_tax_menus.xml',
        'report/report_actions.xml',
        'report/report_tax_declaration.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
