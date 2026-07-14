# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request
from odoo.tools.image import image_data_uri

from odoo.addons.hr_attendance.controllers.main import HrAttendance


class HrAttendanceKioskCheckin(HrAttendance):

    @http.route('/hr_attendance/employees_infos', type="json", auth="public")
    def employees_infos(self, token, limit, offset, domain):
        result = super().employees_infos(token, limit, offset, domain)
        if isinstance(result, dict) and result.get('records'):
            employees = request.env['hr.employee'].sudo().browse(
                [record['id'] for record in result['records']]
            )
            attendance_infos = {
                employee.id: (employee.attendance_state, employee.last_check_in)
                for employee in employees
            }
            for record in result['records']:
                state, last_check_in = attendance_infos[record['id']]
                record['attendance_state'] = state
                record['last_check_in'] = last_check_in
        return result

    @http.route('/hr_attendance/checked_in_employees', type="json", auth="public")
    def checked_in_employees(self, token):
        company = self._get_company(token)
        if company:
            attendances = request.env['hr.attendance'].sudo().search([
                ('employee_id.company_id', '=', company.id),
                ('check_out', '=', False),
            ], order="check_in desc", limit=100)
            return [{
                'id': attendance.employee_id.id,
                'name': attendance.employee_id.name,
                'avatar': image_data_uri(attendance.employee_id.avatar_128),
                'check_in': attendance.check_in,
            } for attendance in attendances]
        return []
