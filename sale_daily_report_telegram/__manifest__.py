# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Daily, Weekly & Monthly Sales Report via Telegram",
    'version': '18.0.3.0.0',
    'category': 'Sales/Sales',
    'summary': "Send daily, weekly & monthly PDF sales reports (Khmer/Chinese) to the boss via Telegram",
    'description': """
Daily, Weekly & Monthly Sales Report via Telegram
====================================================

Every day at 19:00 (Indochina Time, UTC+7, by default), generates a PDF
summarizing that day's confirmed sales orders (order, customer,
salesperson, total) and sends it via Telegram, with a short caption
(order count and total revenue).

Every Monday, a similar PDF covers the previous Monday-Sunday week,
labeled with its ISO week number (e.g. "W28").

On the 1st of each month, a similar PDF covers the previous calendar
month.

All three PDFs are bilingual (Khmer / Chinese) and use a Khmer-
compatible font so labels and headings render correctly for Khmer-
speaking staff.

Requires the "Send by Telegram" module, whose bot token configuration
is reused to send these reports.

Configuration
-------------
* Settings > General Settings > Daily Sales Report: enable/disable
  each report and set the destination Telegram chat ID (e.g. the
  boss's personal chat).
* Settings > Technical > Scheduled Actions: adjust execution times if
  your company is not on Indochina Time (UTC+7) — scheduled action
  times are stored in UTC.
""",
    'author': 'MRDIL ODOO',
    'license': 'LGPL-3',
    'depends': ['sale', 'send_by_telegram'],
    'data': [
        'report/sale_daily_report_templates.xml',
        'report/sale_daily_report_actions.xml',
        'views/res_config_settings_views.xml',
        'data/ir_cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
