# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Daily Attendance Report via Telegram",
    'version': '18.0.1.2.0',
    'category': 'Human Resources/Attendances',
    'summary': "Send daily Telegram reports of attendance, and a late-arrival alert every morning",
    'description': """
Daily Attendance Report via Telegram
=====================================

Every day at 18:30 (Indochina Time, UTC+7, by default), sends a Telegram
message reporting:

* Employees who worked today, with their check-in / check-out times
* Employees who were scheduled to work today but have no attendance
  record (absent)

Every day at 09:01 (Indochina Time, UTC+7, by default), sends a second
Telegram message (e.g. to an all-employees group) listing employees who
are late: no check-in yet past their scheduled start time (+ grace
period), or whose first check-in today came after that threshold.

Requires the "Send by Telegram" module, whose bot token configuration
is reused to send these reports.

Configuration
-------------
* Settings > General Settings > Attendance Telegram Report:
  enable/disable each report, set the destination Telegram chat/group ID(s),
  and the late grace period (minutes).
* Settings > Technical > Scheduled Actions > "Send Daily Attendance Report
  via Telegram" / "Send Late Attendance Alert via Telegram": adjust the
  execution time if your company is not on Indochina Time (UTC+7) —
  scheduled action times are stored in UTC.
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
