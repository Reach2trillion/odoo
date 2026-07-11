# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


def _build_stock_rows(on_hand, locations):
    rows = []
    for product in sorted(on_hand.keys(), key=lambda p: p.name or ''):
        loc_qtys = on_hand[product]
        row = {
            'name': product.name,
            'sku': product.default_code or '',
            'uom': product.uom_id.name,
            'total': sum(loc_qtys.values()),
        }
        for location in locations:
            row[location.id] = loc_qtys.get(location, 0.0)
        rows.append(row)
    return rows


def _build_sold_rows(sold):
    return [
        {
            'name': product.name,
            'sku': product.default_code or '',
            'uom': product.uom_id.name,
            'qty': qty,
        }
        for product, qty in sorted(sold.items(), key=lambda kv: kv[0].name or '')
    ]


def _build_kpis(stock_rows, sold_rows):
    return {
        'sku_count': len(stock_rows),
        'total_on_hand': sum(row['total'] for row in stock_rows),
        'total_sold': sum(row['qty'] for row in sold_rows),
    }


class StockDailyReport(models.AbstractModel):
    _name = 'report.stock_report_telegram.report_stock_daily_document'
    _description = "Daily Stock Report (PDF)"

    def _get_report_values(self, docids, data=None):
        data = data or {}
        Quant = self.env['stock.quant']
        locations = Quant._get_stock_report_locations()
        on_hand = Quant._get_stock_on_hand(locations)
        sold = Quant._get_stock_sold_between(data.get('date_from'), data.get('date_to'), locations)

        stock_rows = _build_stock_rows(on_hand, locations)
        sold_rows = _build_sold_rows(sold)
        return {
            'doc_ids': docids,
            'doc_model': 'stock.quant',
            'company': self.env.company,
            'report_date': data.get('report_date'),
            'locations': locations,
            'stock_rows': stock_rows,
            'sold_rows': sold_rows,
            'kpis': _build_kpis(stock_rows, sold_rows),
        }


class StockWeeklyReport(models.AbstractModel):
    _name = 'report.stock_report_telegram.report_stock_weekly_document'
    _description = "Weekly Stock Report (PDF)"

    def _get_report_values(self, docids, data=None):
        data = data or {}
        Quant = self.env['stock.quant']
        locations = Quant._get_stock_report_locations()
        on_hand = Quant._get_stock_on_hand(locations)
        sold = Quant._get_stock_sold_between(data.get('date_from'), data.get('date_to'), locations)

        stock_rows = _build_stock_rows(on_hand, locations)
        sold_rows = _build_sold_rows(sold)
        return {
            'doc_ids': docids,
            'doc_model': 'stock.quant',
            'company': self.env.company,
            'week_label': data.get('week_label'),
            'locations': locations,
            'stock_rows': stock_rows,
            'sold_rows': sold_rows,
            'kpis': _build_kpis(stock_rows, sold_rows),
        }


class StockMonthlyReport(models.AbstractModel):
    _name = 'report.stock_report_telegram.report_stock_monthly_document'
    _description = "Monthly Stock Report (PDF)"

    def _get_report_values(self, docids, data=None):
        data = data or {}
        Quant = self.env['stock.quant']
        locations = Quant._get_stock_report_locations()
        on_hand = Quant._get_stock_on_hand(locations)
        sold = Quant._get_stock_sold_between(data.get('date_from'), data.get('date_to'), locations)

        stock_rows = _build_stock_rows(on_hand, locations)
        sold_rows = _build_sold_rows(sold)
        return {
            'doc_ids': docids,
            'doc_model': 'stock.quant',
            'company': self.env.company,
            'month_label': data.get('month_label'),
            'locations': locations,
            'stock_rows': stock_rows,
            'sold_rows': sold_rows,
            'kpis': _build_kpis(stock_rows, sold_rows),
        }
