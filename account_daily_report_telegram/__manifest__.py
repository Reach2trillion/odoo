# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Daily, Weekly & Monthly Accounting Report via Telegram",
    'version': '18.0.2.0.0',
    'category': 'Accounting/Accounting',
    'summary': "Send a genz-style accounting dashboard PDF (Khmer/Chinese) to the boss via Telegram",
    'description': """
Accounting Report via Telegram
================================

A dashboard-style PDF (KPI cards + tables), bilingual Khmer/Chinese,
sent automatically via Telegram:

* Daily (every day)
* Weekly (every Monday, covering the previous Mon-Sun week, labeled
  with its ISO week number e.g. "W28")
* Monthly (1st of each month, covering the previous calendar month)

Each report shows:

* Invoices issued (count + total invoiced)
* Payments received in the period (count + total paid in)
* Vendor bills received (count + total expenses)
* Net profit (invoiced - expenses) for the period
* Outstanding receivable (total unpaid/partial customer invoices, as
  of now) and the number of customers who still owe
* A table of customer invoices issued in the period (with payment
  status), on its own page
* A table of the payments received in the period (who paid), plus a
  table of customers who still owe money (biggest debt first), on
  their own page
* A table of vendor bills received in the period, on its own page

Requires the "Send by Telegram" module, whose bot token configuration
is reused to send these reports.

Configuration
-------------
* Settings > General Settings > Accounting Report: enable/disable
  each report and set the destination Telegram chat ID (e.g. the
  boss's personal chat).
* Settings > Technical > Scheduled Actions: adjust execution times if
  your company is not on Indochina Time (UTC+7) — scheduled action
  times are stored in UTC.
""",
    'author': 'MRDIL ODOO',
    'license': 'LGPL-3',
    'depends': ['account', 'send_by_telegram'],
    'data': [
        'report/account_report_templates.xml',
        'report/account_report_actions.xml',
        'views/res_config_settings_views.xml',
        'data/ir_cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
