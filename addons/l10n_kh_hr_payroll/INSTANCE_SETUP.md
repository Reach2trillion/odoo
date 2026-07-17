# How the live ABJ SkinCare instance was configured (2026-07-17)

The production Odoo 18 instance could not install this module as a zip:
its `addons_path` contains **no writable directory** (the MCP installer
returned *"No writable addons directory found in Odoo config addons_path"*).
The complete Cambodia payroll setup was therefore applied **through the API**
as records, functionally equivalent to this module:

## What exists in the database (module namespace `l10n_kh_hr_payroll`)
Every record was registered in `ir.model.data` with the **same XML IDs as the
files in this module**, so a later proper install/upgrade of the module will
match and update them instead of duplicating.

* Salary structure type `structure_type_kh_employee` (id 5) and structure
  `hr_payroll_structure_kh_monthly` (id 4, code `KHMONTHLY`) with the same
  22 salary rules as `data/hr_salary_structure_data.xml`.
* The 10 rule parameters + values of `data/hr_rule_parameter_data.xml`.
* The 8 payslip input types (OT, BONUS, COMMISSION, SENIORITY, NONTAX,
  FRINGE, ADVANCE, DEDUCTION).
* QWeb reports `report_payslip_kh`, `report_contract_kh` (+
  `report_contract_kh_articles` sub-template) and their two report actions,
  with the CSS **inlined in the templates** (no asset bundle without the
  module) and a system-font stack for Khmer.
* Form view extensions for contract / employee / company.

## One structural difference: field names
Without module code, custom fields had to be created as **manual fields**,
which Odoo requires to be prefixed with `x_`. The live instance therefore has
`x_l10n_kh_*` fields (e.g. `x_l10n_kh_housing_allowance` on `hr.contract`,
`x_l10n_kh_tax_dependents` on `hr.employee`,
`x_l10n_kh_tos_exchange_rate` on `res.company`) and the deployed salary-rule
code and report templates reference those `x_` names. This module's source
uses the proper `l10n_kh_*` names.

## Migrating to the real module later
1. Give the Odoo container a writable custom addons directory listed in
   `addons_path` (e.g. mount `/mnt/extra-addons`), copy this module there and
   restart Odoo, then install/upgrade `l10n_kh_hr_payroll`.
2. Copy data from the manual fields to the module fields for each model,
   e.g. in an Odoo shell:
   ```python
   for c in env['hr.contract'].with_context(active_test=False).search([]):
       c.l10n_kh_housing_allowance = c.x_l10n_kh_housing_allowance
       # ... repeat for the other x_l10n_kh_* fields on contract,
       #     employee and company
   ```
3. Update the salary rules' Python code (module upgrade rewrites the
   noupdate rules only if you reset them) and delete the manual `x_l10n_kh_*`
   fields from Settings > Technical > Fields.

## Khmer fonts in PDFs
The API-deployed templates rely on fonts installed on the server
(`Khmer OS`, `Noto Sans Khmer`, `Battambang`, ...). If Khmer characters show
as boxes in the PDF output, install fonts in the Odoo container:
`apt-get install fonts-khmeros fonts-hanuman` (or deploy this module
properly — it ships Noto Sans Khmer and loads it via
`web.report_assets_common`).
