# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AccountDailyReport(models.AbstractModel):
    _name = 'report.account_daily_report_telegram.report_acc_daily_doc'
    _description = "Daily Accounting Report (PDF)"

    def _get_report_values(self, docids, data=None):
        return self.env['account.move']._get_account_report_values(data)


class AccountWeeklyReport(models.AbstractModel):
    _name = 'report.account_daily_report_telegram.report_acc_weekly_doc'
    _description = "Weekly Accounting Report (PDF)"

    def _get_report_values(self, docids, data=None):
        return self.env['account.move']._get_account_report_values(data)


class AccountMonthlyReport(models.AbstractModel):
    _name = 'report.account_daily_report_telegram.report_acc_monthly_doc'
    _description = "Monthly Accounting Report (PDF)"

    def _get_report_values(self, docids, data=None):
        return self.env['account.move']._get_account_report_values(data)
