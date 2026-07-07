# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SaleDailyReport(models.AbstractModel):
    _name = 'report.send_by_telegram.report_sale_daily_document'
    _description = "Daily Sales Report (PDF)"

    @staticmethod
    def _format_amount(amount, currency):
        """Plain ASCII amount string (regular space, no widget-injected
        non-breaking space) to avoid encoding issues in the PDF renderer."""
        formatted = "{:,.2f}".format(amount)
        symbol = currency.symbol or ''
        if currency.position == 'before':
            return "%s %s" % (symbol, formatted)
        return "%s %s" % (formatted, symbol)

    def _get_report_values(self, docids, data=None):
        docs = self.env['sale.order'].browse(docids)
        data = data or {}
        currency = docs[:1].currency_id or self.env.company.currency_id
        total_amount = sum(docs.mapped('amount_total'))

        order_rows = [
            {
                'name': order.name,
                'partner_name': order.partner_id.name,
                'salesperson_name': order.user_id.name,
                'total_display': self._format_amount(
                    order.amount_total, order.currency_id or currency
                ),
            }
            for order in docs
        ]

        return {
            'doc_ids': docids,
            'doc_model': 'sale.order',
            'docs': docs,
            'order_rows': order_rows,
            'report_date': data.get('report_date') or fields.Date.context_today(self),
            'total_amount_display': self._format_amount(total_amount, currency),
            'company': self.env.company,
        }
