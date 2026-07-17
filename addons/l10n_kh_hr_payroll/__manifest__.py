# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Cambodia - Payroll (ប្រព័ន្ធបើកប្រាក់បៀវត្ស កម្ពុជា)',
    'countries': ['kh'],
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'ABJ SkinCare',
    'summary': 'Cambodian payroll: Tax on Salary (ToS), NSSF, Khmer payslip & employment contract',
    'description': """
Cambodia Payroll Localization
=============================
* Monthly salary structure for Cambodia (Tax on Salary progressive brackets,
  NSSF pension / health care / occupational risk contributions).
* Progressive Tax on Salary (ToS) computed in KHR with the official monthly
  brackets and the KHR 150,000 deduction per dependent; flat 20% for
  non-resident taxpayers.
* NSSF contributions on the contributory wage band (KHR 400,000 - 1,200,000):
  employee pension 2%, employer pension 2%, health care 2.6%,
  occupational risk 0.8%.
* All rates and brackets are stored as Salary Rule Parameters so they can be
  updated without code changes when regulations change.
* Bilingual Khmer/English payslip PDF report.
* Bilingual Khmer/English employment contract PDF report (UDC/FDC).
* Cambodia-specific fields on employee (Khmer name, NSSF ID, tax residency,
  dependents) and contract (allowances, contract duration type).
    """,
    'depends': [
        'hr_payroll',
        'hr_contract',
    ],
    'data': [
        'data/hr_rule_parameter_data.xml',
        'data/hr_payslip_input_type_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'report/report_actions.xml',
        'data/hr_salary_structure_data.xml',
        'views/hr_employee_views.xml',
        'views/hr_contract_views.xml',
        'views/res_company_views.xml',
        'report/report_payslip_kh.xml',
        'report/report_contract_kh.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'l10n_kh_hr_payroll/static/src/css/khmer_fonts.css',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
