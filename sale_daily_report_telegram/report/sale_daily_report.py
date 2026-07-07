# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SaleDailyReport(models.AbstractModel):
    _name = 'report.sale_daily_report_telegram.report_sale_daily_document'
    _description = "Daily Sales Report (PDF)"

    def _get_report_values(self, docids, data=None):
        docs = self.env['sale.order'].browse(docids)
        data = data or {}
        return {
            'doc_ids': docids,
            'doc_model': 'sale.order',
            'docs': docs,
            'report_date': data.get('report_date') or fields.Date.context_today(self),
            'total_amount': sum(docs.mapped('amount_total')),
            'currency': docs[:1].currency_id or self.env.company.currency_id,
            'company': self.env.company,
        }
