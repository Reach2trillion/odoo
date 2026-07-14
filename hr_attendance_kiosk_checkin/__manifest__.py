# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Attendance Kiosk: Who Is Checked In',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'sequence': 241,
    'summary': 'Show checked-in employees on the attendance kiosk',
    'description': """
Show who is checked in on the Attendance Kiosk
==============================================

Extends the attendance kiosk without modifying the core hr_attendance module:

- The kiosk main screen displays a "Currently checked in" panel listing
  employees who are checked in, with avatar, name and check-in time.
- Employee cards on the manual selection screen show a green
  "Checked in since ..." badge, or a muted "Checked out" badge.
    """,
    'depends': ['hr_attendance'],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'assets': {
        'web.assets_backend': [
            'hr_attendance_kiosk_checkin/static/src/**/*.js',
            'hr_attendance_kiosk_checkin/static/src/**/*.xml',
        ],
        'hr_attendance.assets_public_attendance': [
            'hr_attendance_kiosk_checkin/static/src/**/*.js',
            'hr_attendance_kiosk_checkin/static/src/**/*.xml',
        ],
    },
}
