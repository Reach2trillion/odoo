# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import timedelta

from odoo import _, api, fields, models

from odoo.addons.send_by_telegram.services.telegram_service import TelegramService

_logger = logging.getLogger(__name__)

CUSTOMER_TYPES = ('out_invoice', 'out_refund')
VENDOR_TYPES = ('in_invoice', 'in_refund')

PAYMENT_STATE_LABELS = {
    'not_paid': 'មិនទាន់បង់ / 未付款',
    'in_payment': 'កំពុងដំណើរការ / 处理中',
    'paid': 'បានបង់ / 已付款',
    'partial': 'បង់ខ្លះ / 部分付款',
    'reversed': 'បានបញ្ច្រាស / 已冲销',
    'invoicing_legacy': '-',
}


def _format_amount(amount, currency):
    """Plain ASCII amount string (regular space, no widget-injected
    non-breaking space) to avoid encoding issues in the PDF renderer."""
    formatted = "{:,.2f}".format(amount)
    symbol = currency.symbol or ''
    if currency.position == 'before':
        return "%s %s" % (symbol, formatted)
    return "%s %s" % (formatted, symbol)


def _build_move_rows(moves, currency, with_payment_state=False):
    rows = []
    for move in moves:
        row = {
            'name': move.name,
            'partner_name': move.partner_id.name or '',
            'total_display': _format_amount(move.amount_total, move.currency_id or currency),
        }
        if with_payment_state:
            row['payment_state_display'] = PAYMENT_STATE_LABELS.get(
                move.payment_state, move.payment_state or '')
        rows.append(row)
    return rows


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _get_account_report_moves(self, date_from, date_to, move_types):
        company = self.env.company
        return self.search([
            ('company_id', '=', company.id),
            ('state', '=', 'posted'),
            ('move_type', 'in', list(move_types)),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
        ], order='invoice_date asc, name asc')

    @api.model
    def _get_outstanding_receivable(self):
        company = self.env.company
        unpaid = self.search([
            ('company_id', '=', company.id),
            ('state', '=', 'posted'),
            ('move_type', 'in', list(CUSTOMER_TYPES)),
            ('payment_state', 'in', ('not_paid', 'partial')),
        ])
        return sum(unpaid.mapped('amount_residual'))

    @api.model
    def _get_account_report_values(self, data):
        """Shared by all 3 report AbstractModels (daily/weekly/monthly) -
        the data dict always carries pre-computed move ids so the report
        template doesn't need to re-derive the period's date range."""
        data = data or {}
        currency = self.env.company.currency_id
        customer_moves = self.browse(data.get('customer_move_ids', []))
        vendor_moves = self.browse(data.get('vendor_move_ids', []))

        total_invoiced = sum(customer_moves.mapped('amount_total'))
        total_expenses = sum(vendor_moves.mapped('amount_total'))
        net_profit = total_invoiced - total_expenses
        outstanding = self._get_outstanding_receivable()

        return {
            'doc_ids': [],
            'doc_model': 'account.move',
            'company': self.env.company,
            'period_label': data.get('period_label'),
            'customer_rows': _build_move_rows(customer_moves, currency, with_payment_state=True),
            'vendor_rows': _build_move_rows(vendor_moves, currency, with_payment_state=False),
            'kpis': {
                'invoice_count': len(customer_moves),
                'bill_count': len(vendor_moves),
                'total_invoiced_display': _format_amount(total_invoiced, currency),
                'total_expenses_display': _format_amount(total_expenses, currency),
                'net_profit_display': _format_amount(net_profit, currency),
                'outstanding_display': _format_amount(outstanding, currency),
            },
        }

    @staticmethod
    def _split_telegram_chat_ids(chat_id):
        """Allow a comma-separated list of chat IDs (e.g. one per boss)."""
        return [part.strip() for part in (chat_id or '').split(',') if part.strip()]

    @api.model
    def _send_account_report_telegram(self, date_from, date_to, period_label,
                                       action_xmlid, filename, caption_title):
        icp = self.env['ir.config_parameter'].sudo()
        chat_id = icp.get_param('account_daily_report_telegram.chat_id')
        token = icp.get_param('send_by_telegram.bot_token')
        if not chat_id or not token:
            _logger.warning(
                "Accounting Telegram report is not fully configured "
                "(missing bot token or chat id); skipping."
            )
            return

        customer_moves = self._get_account_report_moves(date_from, date_to, CUSTOMER_TYPES)
        vendor_moves = self._get_account_report_moves(date_from, date_to, VENDOR_TYPES)

        total_invoiced = sum(customer_moves.mapped('amount_total'))
        total_expenses = sum(vendor_moves.mapped('amount_total'))
        net_profit = total_invoiced - total_expenses
        outstanding = self._get_outstanding_receivable()
        currency = self.env.company.currency_id

        pdf_content, dummy = self.env['ir.actions.report']._render_qweb_pdf(
            action_xmlid,
            [],
            data={
                'period_label': period_label,
                'customer_move_ids': customer_moves.ids,
                'vendor_move_ids': vendor_moves.ids,
            },
        )
        caption = _(
            "%(title)s\n\n"
            "🧾 Invoices: <b>%(inv_count)s</b> · %(invoiced)s %(cur)s\n"
            "📤 Bills: <b>%(bill_count)s</b> · %(expenses)s %(cur)s\n"
            "💰 Net: <b>%(profit)s %(cur)s</b>\n"
            "⏳ Outstanding: <b>%(outstanding)s %(cur)s</b>"
        ) % {
            'title': caption_title,
            'inv_count': len(customer_moves),
            'invoiced': "{:,.2f}".format(total_invoiced),
            'bill_count': len(vendor_moves),
            'expenses': "{:,.2f}".format(total_expenses),
            'profit': "{:,.2f}".format(net_profit),
            'outstanding': "{:,.2f}".format(outstanding),
            'cur': currency.symbol,
        }

        service = TelegramService(token)
        for recipient_chat_id in self._split_telegram_chat_ids(chat_id):
            service.send_document(
                chat_id=recipient_chat_id,
                document_content=pdf_content,
                filename=filename,
                caption=caption,
            )

    @api.model
    def _cron_send_daily_account_report_telegram(self):
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param('account_daily_report_telegram.enabled', 'True') != 'True':
            return

        report_date = fields.Date.context_today(self)
        self._send_account_report_telegram(
            date_from=report_date,
            date_to=report_date,
            period_label=report_date.strftime('%d/%m/%Y'),
            action_xmlid='account_daily_report_telegram.action_report_account_daily',
            filename=_("Daily_Accounting_Report_%s.pdf") % report_date.strftime('%Y%m%d'),
            caption_title=_("📒 <b>Daily Accounting Report — %s</b>") % report_date.strftime('%d/%m/%Y'),
        )

    @api.model
    def _cron_send_weekly_account_report_telegram(self):
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param('account_daily_report_telegram.weekly_enabled', 'True') != 'True':
            return

        today = fields.Date.context_today(self)
        this_monday = today - timedelta(days=today.weekday())
        week_start = this_monday - timedelta(days=7)
        week_end = this_monday - timedelta(days=1)
        week_number = week_start.isocalendar()[1]
        period_label = 'W%s · %s - %s' % (
            week_number, week_start.strftime('%d/%m/%Y'), week_end.strftime('%d/%m/%Y'))

        self._send_account_report_telegram(
            date_from=week_start,
            date_to=week_end,
            period_label=period_label,
            action_xmlid='account_daily_report_telegram.action_report_account_weekly',
            filename=_("Weekly_Accounting_Report_W%s_%s.pdf") % (week_number, week_start.strftime('%Y%m%d')),
            caption_title=_("📒 <b>Weekly Accounting Report — %s</b>") % period_label,
        )

    @api.model
    def _cron_send_monthly_account_report_telegram(self):
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param('account_daily_report_telegram.monthly_enabled', 'True') != 'True':
            return

        today = fields.Date.context_today(self)
        first_of_this_month = today.replace(day=1)
        month_end = first_of_this_month - timedelta(days=1)
        month_start = month_end.replace(day=1)
        month_label = month_start.strftime('%B %Y')

        self._send_account_report_telegram(
            date_from=month_start,
            date_to=month_end,
            period_label=month_label,
            action_xmlid='account_daily_report_telegram.action_report_account_monthly',
            filename=_("Monthly_Accounting_Report_%s.pdf") % month_start.strftime('%Y%m'),
            caption_title=_("📒 <b>Monthly Accounting Report — %s</b>") % month_label,
        )
