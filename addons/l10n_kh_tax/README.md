# Cambodia - Accounting & Tax Reporting (l10n_kh_tax)

Odoo 18 module for Cambodian tax compliance with the **General Department of
Taxation (GDT)**: a self-contained **GDT Tax Ledger** the government checks
(independent from the Odoo accounting), monthly and annual declarations,
VAT / Withholding Tax / Prepayment of Tax on Income, and **e-Filing** export.

## Key concept: the tax book the government checks

The **GDT Tax Ledger** (*Cambodia Tax → GDT Tax Ledger*) is a separate tax
book that contains **only** what is reported to the tax administration — the
rest of the Odoo accounting is excluded:

* When a monthly declaration is computed, the ledger is synchronised from
  the **reportable** Odoo documents only: posted entries not flagged
  *Exclude from Cambodia Tax Report*; non-VAT income is taken only from
  accounts flagged *Report to GDT (Cambodia)* (income carrying a Cambodian
  VAT tax is always declared through the VAT registers, as required — use
  the entry-level exclude flag for documents that must stay out entirely).
* **Manual entries** can be added directly in the tax book without touching
  the Odoo accounting.
* Confirming a declaration **locks** its ledger entries — a tamper-proof
  audit trail for the government inspection.
* A dedicated **Government Auditor (GDT)** security group gives the
  inspector **read-only** access to the tax book and the declarations, and
  **no access** to the rest of the Odoo accounting.

## Features

### 1. Cambodian taxes created automatically
VAT 10% (sales/purchases), VAT 0% (export), WHT 10% rent, WHT 15% services
and royalties, WHT 6%/4% interest, WHT 14% non-resident, Accommodation Tax
2%, Public Lighting Tax 3%. Additional categories are available for mapping
your own taxes: reverse-charge VAT (e-commerce), Tax on Salary, Fringe
Benefit Tax 20%, Specific Tax, Advance Tax on Dividend Distribution.

### 2. Choose what is reported to the GDT
* **Account level** — *Report to GDT (Cambodia)* checkbox on every account
  (*Configuration → GDT Reportable Accounts*).
* **Entry level** — *Exclude from Cambodia Tax Report* checkbox on every
  invoice, bill or payment.

### 3. Monthly Tax Declaration (auto-generated)
Created automatically on the 1st of each month by a scheduled action and
computed **from the tax ledger**:

* PRE01 — Prepayment of Tax on Income 1% of taxable turnover
* WHT01-06 — Withholding taxes (resident & non-resident)
* VAT01-06 — Output, input, credit brought forward from the previous
  month, payable, credit carried forward, reverse charge
* TOS01-02 — Tax on Salary (from Cambodian payroll) & Fringe Benefit Tax
* OTH01-05 — Accommodation, Public Lighting, Specific, Dividend, other

Amounts are converted to **KHR** with the official monthly exchange rate.
The PDF declaration includes the **sales, purchase, withholding and salary
registers as annexes** for the government inspection.

### 4. Annual Tax on Income declaration
20% Tax on Income vs 1% Minimum Tax (with exemption flag), credit of the
monthly PToI prepayments, balance payable / credit carried forward, and the
annual Patent Tax by taxpayer classification. Printable bilingual PDF.

### 5. e-Filing
The **Export e-Filing (Excel)** button produces a workbook with the Sales,
Purchases, Withholding Tax and Salary & Other registers (document number,
TIN, partner, base, tax, totals, KHR) following the GDT e-Filing upload
template, attached to the declaration for the audit trail.

### 6. Audit support
* Workflow **Draft → Confirmed → Filed**; confirmed declarations lock their
  ledger entries and cannot be deleted; full chatter/tracking, filed date &
  user, audit notes.
* Security groups: **Tax Officer**, **Tax Manager**, **Government Auditor
  (GDT)** (read-only on the tax book and declarations; no access to the
  Odoo accounting). Note: the auditor is still a regular internal user —
  like any employee login they can read shared data such as contacts. For a
  stricter setup, hand the auditor the printed declaration with its
  register annexes and the e-Filing export instead of a login.

## Configuration
1. Install the module (application *Cambodia Tax* in the main menu).
2. Company form → **Cambodia Tax (GDT)** tab: TIN, taxpayer classification,
   tax branch, e-Filing account, default KHR rate.
3. Review *Configuration → GDT Reportable Accounts* and untick the accounts
   that must not be reported.
4. Give the tax inspector a user in the **Government Auditor (GDT)** group.

## Legal references
* Law on Taxation (as amended) & annual Laws on Financial Management
* Prakas on VAT (10%), Prakas 372 on Withholding Tax, Prakas on ToS
* Monthly declarations due by the **25th of the following month** via the
  GDT e-Filing system (https://efiling.tax.gov.kh); the annual ToI return
  within **3 months** of the year end.

> This module is a compliance aid. Always verify the declarations with your
> tax advisor before filing; rates and forms may change with new Prakas.
