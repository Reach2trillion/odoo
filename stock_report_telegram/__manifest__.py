# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Daily, Weekly & Monthly Stock Report via Telegram",
    'version': '18.0.2.0.0',
    'category': 'Inventory/Inventory',
    'summary': "Send daily, weekly & monthly stock-on-hand PDF reports (bilingual English/Khmer) to the boss via Telegram",
    'description': """
Stock Report via Telegram
==========================

Daily report (every day, time configurable via Scheduled Actions):

* Stock on hand per product, for up to 2 tracked locations (e.g.
  Warehouse and Office Sale Stock), with a total column
* Stock sold today (quantity that left the tracked locations to a
  customer today)

Weekly report (every Monday, time configurable via Scheduled Actions):

* Current stock on hand per product/location
* Total quantity sold during the previous Monday-Sunday week

Monthly report (1st of each month, time configurable via Scheduled
Actions):

* Current stock on hand per product/location
* Total quantity sold during the previous month

All three PDFs are bilingual (English / Khmer) and use a Khmer-
compatible font so labels and headings render correctly for Khmer-
speaking staff.

Requires the "Send by Telegram" module, whose bot token configuration
is reused to send these reports.

Configuration
-------------
* Settings > General Settings > Stock Report: enable/disable each
  report, set the destination Telegram chat ID, and pick the two
  stock locations to track.
* Settings > Technical > Scheduled Actions: adjust execution times if
  your company is not on Indochina Time (UTC+7) — scheduled action
  times are stored in UTC.
""",
    'author': 'MRDIL ODOO',
    'license': 'LGPL-3',
    'depends': ['stock', 'send_by_telegram'],
    'data': [
        'report/stock_report_templates.xml',
        'report/stock_report_actions.xml',
        'views/res_config_settings_views.xml',
        'data/ir_cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
