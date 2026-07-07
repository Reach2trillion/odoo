# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Daily Attendance Report via Telegram",
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'summary': "Send a daily Telegram report of who worked, how long, and who was absent",
    'description': """
Daily Attendance Report via Telegram
=====================================

Every day at 18:30 (Indochina Time, UTC+7, by default), sends a Telegram
message reporting:

* Employees who worked today, with total hours worked
* Employees who were scheduled to work today but have no attendance
  record (absent)

Requires the "Send by Telegram" module, whose bot token configuration
is reused to send this report.

Configuration
-------------
* Settings > General Settings > Attendance Telegram Report:
  enable/disable the report and set the destination Telegram chat/group ID.
* Settings > Technical > Scheduled Actions > "Send Daily Attendance Report
  via Telegram": adjust the execution time if your company is not on
  Indochina Time (UTC+7) — scheduled action times are stored in UTC.
""",
    'author': 'MRDIL ODOO',
    'license': 'LGPL-3',
    'depends': ['hr_attendance', 'send_by_telegram'],
    'data': [
        'views/res_config_settings_views.xml',
        'data/ir_cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
