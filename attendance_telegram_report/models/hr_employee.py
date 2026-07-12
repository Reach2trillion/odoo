# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime, time, timedelta

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
                att.employee_id.id,
                {'check_in': None, 'check_out': None, 'still_working': False},
            )
            check_in = max(att.check_in, day_start_utc)
            if session['check_in'] is None or check_in < session['check_in']:
                session['check_in'] = check_in

            if not att.check_out:
                # An open attendance means the employee is currently checked in.
                session['still_working'] = True
            else:
                check_out = min(att.check_out, day_end_utc)
                if session['check_out'] is None or check_out > session['check_out']:
                    session['check_out'] = check_out

        present_data = sorted(
            (
                {
                    'employee': self.browse(emp_id),
                    'check_in': session['check_in'],
                    'check_out': None if session['still_working'] else session['check_out'],
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

    def _get_telegram_expected_start_time(self, report_date, tz):
        """Return the employee's scheduled start time on report_date, in UTC (naive)."""
        self.ensure_one()
        calendar = self.resource_calendar_id
        if not calendar:
            return None
        weekday = str(report_date.weekday())
        day_attendances = calendar.attendance_ids.filtered(lambda a: a.dayofweek == weekday)
        if not day_attendances:
            return None
        hour_from = min(day_attendances.mapped('hour_from'))
        hours, minutes = divmod(int(round(hour_from * 60)), 60)
        local_dt = tz.localize(datetime.combine(report_date, time(hour=hours, minute=minutes)))
        return local_dt.astimezone(pytz.UTC).replace(tzinfo=None)

    @api.model
    def _get_telegram_late_employees(self, report_date=None, reference_time_utc=None):
        """Employees scheduled to work today who are late.

        "Late" means: no check-in yet past their scheduled start time (+ grace
        period), or their first check-in today was after that threshold.

        Returns:
            list[dict]: [{'employee': hr.employee, 'check_in': datetime (UTC) or None}, ...]
        """
        company = self.env.company
        tz = self._get_telegram_report_tz()
        report_date = report_date or fields.Date.context_today(self)
        reference_time_utc = reference_time_utc or datetime.utcnow()

        grace_minutes = int(self.env['ir.config_parameter'].sudo().get_param(
            'attendance_telegram_report.late_grace_minutes', 0
        ) or 0)

        employees = self.search([('company_id', '=', company.id)])
        scheduled_employees = employees.filtered(
            lambda e: e._is_telegram_report_working_day(report_date)
        )

        day_start_utc = tz.localize(datetime.combine(report_date, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        day_end_utc = tz.localize(datetime.combine(report_date, time.max)).astimezone(pytz.UTC).replace(tzinfo=None)

        attendances = self.env['hr.attendance'].search([
            ('employee_id', 'in', scheduled_employees.ids),
            ('check_in', '>=', day_start_utc),
            ('check_in', '<=', day_end_utc),
        ], order='check_in asc')

        first_check_in = {}
        for att in attendances:
            first_check_in.setdefault(att.employee_id.id, att.check_in)

        late_employees = []
        for employee in scheduled_employees:
            expected_start = employee._get_telegram_expected_start_time(report_date, tz)
            if expected_start is None:
                continue
            threshold_utc = expected_start + timedelta(minutes=grace_minutes)

            check_in = first_check_in.get(employee.id)
            if check_in is None:
                if reference_time_utc > threshold_utc:
                    late_employees.append({'employee': employee, 'check_in': None})
            elif check_in > threshold_utc:
                late_employees.append({'employee': employee, 'check_in': check_in})

        late_employees.sort(key=lambda data: data['employee'].name or '')
        return late_employees

    @api.model
    def _get_telegram_late_report_text(self, report_date=None, reference_time_utc=None):
        report_date = report_date or fields.Date.context_today(self)
        late_employees = self._get_telegram_late_employees(report_date, reference_time_utc)
        if not late_employees:
            return None

        tz = self._get_telegram_report_tz()
        lines = "\n".join(
            "⏰ %(name)s — %(status)s"
            % {
                'name': data['employee'].name,
                'status': (
                    _("checked in at %s") % self._format_telegram_report_time(data['check_in'], tz)
                    if data['check_in'] else _("not checked in yet")
                ),
            }
            for data in late_employees
        )

        return _(
            "🚨 <b>Late Attendance Alert — %(date)s</b>\n\n%(lines)s"
        ) % {
            'date': report_date.strftime('%d/%m/%Y'),
            'lines': lines,
        }

    @api.model
    def _cron_send_telegram_late_report(self):
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param('attendance_telegram_report.late_enabled', 'True') != 'True':
            return

        chat_id = (
            icp.get_param('attendance_telegram_report.late_chat_id')
            or icp.get_param('attendance_telegram_report.chat_id')
        )
        token = icp.get_param('send_by_telegram.bot_token')
        if not chat_id or not token:
            _logger.warning(
                "Late attendance Telegram alert is not fully configured "
                "(missing bot token or chat id); skipping."
            )
            return

        message = self._get_telegram_late_report_text()
        if not message:
            return
        TelegramService(token).send_message(chat_id=chat_id, text=message)

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
