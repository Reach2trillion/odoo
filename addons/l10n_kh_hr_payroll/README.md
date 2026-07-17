# Cambodia — Payroll (l10n_kh_hr_payroll)

Cambodian payroll localization for **Odoo 18 Enterprise** (`hr_payroll`), with a
bilingual **Khmer/English payslip** and **Khmer/English employment contract** PDF.

## What it provides

### Salary structure — *Cambodia: Monthly Salary (KHMONTHLY)*
| Rule | Code | Basis |
|---|---|---|
| Basic Salary | `BASIC` | Prorated contract wage (`payslip.paid_amount`) |
| Housing / Transport / Meal / Phone / Other allowances | `HOUSING…OTHALW` | Contract "Cambodia" tab (taxable) |
| Overtime / Bonus / Commission | `OT`, `BONUS`, `COMMISSION` | Payslip *Other Inputs* (taxable) |
| Taxable Gross | `GROSS` | Basic + taxable allowances |
| NSSF Pension — employee 2% | `NSSFPEE` | Contributory wage clamped to KHR 400,000–1,200,000 |
| Tax on Salary | `TOS` | Progressive monthly brackets in KHR (see below) |
| Non-taxable allowance / Seniority payment / Other non-taxable income | `NONTAXALW`, `SENIORITY`, `NONTAX` | Paid after tax |
| Salary advance recovery / Other deduction | `ADVANCE`, `OTHDED` | Payslip *Other Inputs* |
| Net Salary | `NET` | Basic + allowances + deductions |
| NSSF employer: Occupational Risk 0.8%, Health Care 2.6%, Pension 2% | `NSSFORC`, `NSSFH`, `NSSFPER` | Employer cost, not deducted from salary |
| Fringe Benefit Tax 20% (employer) | `FBT` | On the `FRINGE` other input |

### Tax on Salary (residents, monthly, KHR) — since Jan 2023
| Monthly taxable salary (KHR) | Rate |
|---|---|
| 0 – 1,500,000 | 0% |
| 1,500,001 – 2,000,000 | 5% |
| 2,000,001 – 8,500,000 | 10% |
| 8,500,001 – 12,500,000 | 15% |
| Over 12,500,000 | 20% |

* KHR 150,000/month deducted from the taxable base **per dependent** (minor
  children, non-working spouse) — set the count on the employee's HR Settings tab.
* The employee NSSF pension contribution is deducted from the taxable base.
* **Non-residents**: flat 20%.
* All brackets/rates/caps live in **Payroll ▸ Configuration ▸ Rule Parameters**
  (codes `l10n_kh_*`) — update them there when regulations change, no code needed.

### Currency handling
Payslips are computed in the company currency (USD for ABJ SkinCare). ToS and
NSSF are computed in KHR using the **ToS Exchange Rate** field on the company
(default **4,100 KHR per USD** — update it monthly with the official GDT rate;
set to 1 if your company currency is KHR).

### Reports (Khmer + English)
* **Payslip (Khmer)** — printed from a payslip (also set as the default report
  of the Cambodia structure): earnings, deductions, net, employer NSSF section,
  signatures.
* **Employment Contract (Khmer)** — printed from a contract (Print menu):
  11-article bilingual contract following the Cambodian Labor Law (FDC/UDC,
  probation, 48h week, 18 days annual leave, NSSF & ToS withholding, termination,
  Khmer text prevails). **Have it reviewed by your lawyer before signing.**

Both reports embed the **Noto Sans Khmer** font (OFL licensed, see
`static/fonts/OFL.txt`) so Khmer renders in PDF. If glyphs are missing on your
server, also install system fonts: `apt-get install fonts-khmeros fonts-noto-core`.

## Setup after install
1. **Company** (Settings ▸ Companies): check *ToS Exchange Rate (KHR per
   currency unit)* — default 4100.
2. **Employees** (HR Settings tab ▸ Cambodia): Khmer name, NSSF ID, tax
   residency, number of tax dependents.
3. **Contracts**: create a contract per employee, pick salary structure type
   **Cambodia: Employee (បុគ្គលិក)** (the *Cambodia: Monthly Salary* structure is
   its default), set the wage in USD, fill the *Cambodia* tab allowances,
   FDC/UDC and workplace, then set the contract to *Running*.
4. **Payslips**: Payroll ▸ Payslips ▸ New — pick the employee, the structure is
   selected automatically; add Other Inputs (overtime, bonus, seniority,
   advances…) as needed; *Compute Sheet* ▸ print **Payslip (Khmer)**.

## Worked example (resident, no dependents, USD, rate 4,100)
Wage $500 + $50 transport ⇒ Gross $550 = KHR 2,255,000
* NSSF employee pension: 2% × 1,200,000 (cap) = KHR 24,000 ≈ **$5.85**
* Taxable: 2,255,000 − 24,000 = 2,231,000 ⇒ ToS = 500,000×5% + 231,000×10% =
  KHR 48,100 ≈ **$11.73**
* Net ≈ **$532.42** · Employer NSSF: 0.8% + 2.6% + 2% × 1,200,000 = KHR 64,800 ≈ $15.80

## Disclaimer
Rates and legal texts reflect regulations as of mid-2026 (ToS brackets of
Sub-Decree 196/2022, NSSF pension phase 1). Always confirm current rates with
the GDT/NSSF or your accountant; adjust the rule parameters if they change.
