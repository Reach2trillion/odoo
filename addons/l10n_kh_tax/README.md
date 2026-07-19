# Cambodia - Accounting & Tax Reporting (l10n_kh_tax)

Odoo 18 module for Cambodian monthly tax compliance with the **General
Department of Taxation (GDT)**: VAT, Withholding Tax, Prepayment of Tax on
Income, monthly declaration and **e-Filing** export.

## Features

### 1. Cambodian taxes created automatically
On installation (and for every new Cambodian company), the module creates the
taxes required by the Law on Taxation, each mapped to a **Cambodia Tax
Category** that feeds the monthly declaration:

| Tax | Rate | Type |
|---|---|---|
| VAT Output (Sales) | 10% | Sale |
| VAT Zero-rated (Export) | 0% | Sale |
| VAT Input (Purchases) | 10% | Purchase |
| WHT Rental (Resident) | 10% | Purchase (withheld) |
| WHT Services (Resident) | 15% | Purchase (withheld) |
| WHT Royalties (Resident) | 15% | Purchase (withheld) |
| WHT Fixed Deposit Interest | 6% | Purchase (withheld) |
| WHT Saving Interest | 4% | Purchase (withheld) |
| WHT Non-Resident | 14% | Purchase (withheld) |
| Accommodation Tax | 2% | Sale |
| Public Lighting Tax | 3% | Sale |

### 2. Choose what is reported to the GDT
* **Account level** — every account has a **Report to GDT (Cambodia)**
  checkbox. Only selected accounts feed the taxable turnover (basis of the 1%
  Prepayment of Tax on Income). Untick it for payments/accounts that must not
  be reported. Manage them from *Cambodia Tax > Configuration > GDT
  Reportable Accounts*.
* **Entry level** — every invoice, bill or payment has an **Exclude from
  Cambodia Tax Report** checkbox to keep a single document out of the
  declaration and the e-Filing export.

### 3. Monthly Tax Declaration (auto-generated)
A scheduled action creates the declaration of the previous month on the 1st
of each month for every Cambodian company, computed from posted entries:

* **PRE01** — Prepayment of Tax on Income, 1% of monthly taxable turnover
* **WHT01-06** — Withholding taxes (resident & non-resident)
* **VAT01-04** — Output VAT, Input VAT, VAT payable / credit carried forward
* **OTH01-03** — Accommodation Tax, Public Lighting Tax, Specific Tax
* **TOS01** — Tax on Salary (pulled from Cambodian payroll when installed)

Amounts are shown in company currency and converted to **KHR** using the
official monthly exchange rate entered on the declaration.

### 4. e-Filing
The **Export e-Filing (Excel)** button generates a workbook with the sales
and purchase transaction lists (invoice number, customer/supplier TIN, base,
VAT, total, KHR total) following the GDT e-Filing upload template, attached
to the declaration for the audit trail.

### 5. Audit support
* Workflow **Draft → Confirmed → Filed**; filed declarations are locked.
* Full chatter/tracking history, filed date & user, audit notes tab.
* **Tax Officer** and **Tax Manager / Auditor** security groups.
* Printable bilingual Khmer/English declaration (PDF).

## Configuration
1. Install the module (application *Cambodia Tax* appears in the main menu).
2. On the company form, tab **Cambodia Tax (GDT)**: fill the TIN, taxpayer
   classification, tax branch, e-Filing account and default KHR rate.
3. Review *Configuration > GDT Reportable Accounts* and untick the accounts
   that must not be reported.
4. Use the Cambodian taxes on your invoices/bills as usual.

## Legal references
* Law on Taxation (as amended) & Law on Financial Management
* Prakas on VAT (10%), Prakas 372 on Withholding Tax
* Monthly declarations due by the **25th of the following month** via the
  GDT e-Filing system (https://efiling.tax.gov.kh)

> This module is a compliance aid. Always verify the declaration with your
> tax advisor before filing; rates and forms may change with new Prakas.
