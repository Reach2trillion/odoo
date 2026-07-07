# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime, time

import pytz

from odoo import _, api, fields, models

from odoo.addons.send_by_telegram.services.telegram_service import TelegramService

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _is_telegram_report_working_day(self, report_date):
        """Best-effort check of whether the employee is scheduled to work on report_date."""
        self.ensure_one()
        calendar = self.resource_calendar_id
        if not calendar:
            return True
        weekday = str(report_date.weekday())
        return bool(calendar.attendance_ids.filtered(lambda a: a.dayofweek == weekday))

    @api.model
    def _get_telegram_report_tz(self):
        company = self.env.company
        tz_name = company.resource_calendar_id.tz or self.env.user.tz or 'UTC'
        return pytz.timezone(tz_name)

    @api.model
    def _get_telegram_attendance_report_data(self, report_date=None):
        """Compute who worked today (check-in/check-out times) and who was absent.

        Returns:
            tuple: (present_data, absent_employees)
                present_data (list[dict]): [{
                    'employee': hr.employee,
                    'check_in': datetime (UTC),
                    'check_out': datetime (UTC) or None if still checked in,
                }, ...]
                absent_employees (hr.employee recordset)
        """
        company = self.env.company
        tz = self._get_telegram_report_tz()

        report_date = report_date or fields.Date.context_today(self)
        day_start_utc = tz.localize(datetime.combine(report_date, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        day_end_utc = tz.localize(datetime.combine(report_date, time.max)).astimezone(pytz.UTC).replace(tzinfo=None)

        employees = self.search([('company_id', '=', company.id)])
        attendances = self.env['hr.attendance'].search([
            ('employee_id', 'in', employees.ids),
            ('check_in', '<=', day_end_utc),
            '|', ('check_out', '=', False), ('check_out', '>=', day_start_utc),
        ], order='check_in asc')

        sessions = {}
        for att in attendances:
            session = sessions.setdefault(
                att.employee_id.id, {'check_in': None, 'check_out': None}
            )
            check_in = max(att.check_in, day_start_utc)
            if session['check_in'] is None or check_in < session['check_in']:
                session['check_in'] = check_in

            if not att.check_out:
                session['check_out'] = None
            elif session['check_out'] is not None:
                check_out = min(att.check_out, day_end_utc)
                if check_out > session['check_out']:
                    session['check_out'] = check_out

        present_data = sorted(
            (
                {
                    'employee': self.browse(emp_id),
                    'check_in': session['check_in'],
                    'check_out': session['check_out'],
                }
                for emp_id, session in sessions.items()
            ),
            key=lambda data: data['employee'].name or '',
        )

        present_employee_ids = set(sessions.keys())
        candidates = employees.filtered(lambda e: e.id not in present_employee_ids)
        absent_employees = candidates.filtered(
            lambda e: e._is_telegram_report_working_day(report_date)
        )

        return present_data, absent_employees

    def _format_telegram_report_time(self, dt_utc, tz):
        return pytz.UTC.localize(dt_utc).astimezone(tz).strftime('%H:%M')

    @api.model
    def _get_telegram_attendance_report_text(self, report_date=None):
        report_date = report_date or fields.Date.context_today(self)
        present_data, absent_employees = self._get_telegram_attendance_report_data(report_date)
        tz = self._get_telegram_report_tz()

        present_lines = "\n".join(
            "✅ %(name)s — %(in_label)s: <b>%(check_in)s</b>, %(out_label)s: <b>%(check_out)s</b>"
            % {
                'name': data['employee'].name,
                'in_label': _("Check In"),
                'check_in': self._format_telegram_report_time(data['check_in'], tz),
                'out_label': _("Check Out"),
                'check_out': (
                    self._format_telegram_report_time(data['check_out'], tz)
                    if data['check_out'] else _("still working")
                ),
            }
            for data in present_data
        ) or _("(none)")

        absent_lines = "\n".join(
            "❌ %s" % emp.name for emp in absent_employees
        ) or _("(none)")

        return _(
            "📋 <b>Daily Attendance Report — %(date)s</b>\n\n"
            "🟢 <b>Worked today (%(present_count)s)</b>\n%(present_lines)s\n\n"
            "🔴 <b>Absent today (%(absent_count)s)</b>\n%(absent_lines)s"
        ) % {
            'date': report_date.strftime('%d/%m/%Y'),
            'present_count': len(present_data),
            'present_lines': present_lines,
            'absent_count': len(absent_employees),
            'absent_lines': absent_lines,
        }

    @api.model
    def _cron_send_daily_telegram_attendance_report(self):
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param('attendance_telegram_report.enabled', 'True') != 'True':
            return

        chat_id = icp.get_param('attendance_telegram_report.chat_id')
        token = icp.get_param('send_by_telegram.bot_token')
        if not chat_id or not token:
            _logger.warning(
                "Attendance Telegram report is not fully configured "
                "(missing bot token or chat id); skipping."
            )
            return

        message = self._get_telegram_attendance_report_text()
        TelegramService(token).send_message(chat_id=chat_id, text=message)
