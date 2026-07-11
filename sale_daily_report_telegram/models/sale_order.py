# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models

from odoo.addons.send_by_telegram.services.telegram_service import TelegramService

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def _get_sale_daily_report_tz(self):
        tz_name = self.env.company.partner_id.tz or self.env.user.tz or 'UTC'
        return pytz.timezone(tz_name)

    @api.model
    def _get_daily_sales_orders(self, report_date=None):
        """Confirmed sales orders for report_date (company timezone)."""
        company = self.env.company
        tz = self._get_sale_daily_report_tz()
        report_date = report_date or fields.Date.context_today(self)

        day_start_utc = tz.localize(datetime.combine(report_date, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        day_end_utc = tz.localize(datetime.combine(report_date, time.max)).astimezone(pytz.UTC).replace(tzinfo=None)

        return self.search([
            ('company_id', '=', company.id),
            ('state', '=', 'sale'),
            ('date_order', '>=', day_start_utc),
            ('date_order', '<=', day_end_utc),
        ], order='date_order asc')

    @staticmethod
    def _split_telegram_chat_ids(chat_id):
        """Allow a comma-separated list of chat IDs (e.g. one per boss)."""
        return [part.strip() for part in (chat_id or '').split(',') if part.strip()]

    @api.model
    def _get_daily_sales_caption_text(self, report_date, orders):
        total_amount = sum(orders.mapped('amount_total'))
        currency = orders[:1].currency_id or self.env.company.currency_id
        return _(
            "📊 <b>Daily Sales Report — %(date)s</b>\n\n"
            "🧾 Orders: <b>%(count)s</b>\n"
            "💰 Total Revenue: <b>%(total)s %(currency)s</b>"
        ) % {
            'date': report_date.strftime('%d/%m/%Y'),
            'count': len(orders),
            'total': "{:,.2f}".format(total_amount),
            'currency': currency.symbol,
        }

    @api.model
    def _get_weekly_sales_orders(self, week_start, week_end):
        """Confirmed sales orders between week_start and week_end (company timezone)."""
        company = self.env.company
        tz = self._get_sale_daily_report_tz()

        week_start_utc = tz.localize(datetime.combine(week_start, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        week_end_utc = tz.localize(datetime.combine(week_end, time.max)).astimezone(pytz.UTC).replace(tzinfo=None)

        return self.search([
            ('company_id', '=', company.id),
            ('state', '=', 'sale'),
            ('date_order', '>=', week_start_utc),
            ('date_order', '<=', week_end_utc),
        ], order='date_order asc')

    @api.model
    def _get_weekly_sales_caption_text(self, week_number, week_start, week_end, orders):
        total_amount = sum(orders.mapped('amount_total'))
        currency = orders[:1].currency_id or self.env.company.currency_id
        return _(
            "📊 <b>W%(week)s · %(start)s - %(end)s</b>\n\n"
            "🧾 Orders: <b>%(count)s</b>\n"
            "💰 Total Revenue: <b>%(total)s %(currency)s</b>"
        ) % {
            'week': week_number,
            'start': week_start.strftime('%d/%m/%Y'),
            'end': week_end.strftime('%d/%m/%Y'),
            'count': len(orders),
            'total': "{:,.2f}".format(total_amount),
            'currency': currency.symbol,
        }

    @api.model
    def _cron_send_weekly_sales_report_telegram(self):
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param('sale_daily_report_telegram.weekly_enabled', 'True') != 'True':
            return

        chat_id = icp.get_param('sale_daily_report_telegram.chat_id')
        token = icp.get_param('send_by_telegram.bot_token')
        if not chat_id or not token:
            _logger.warning(
                "Weekly sales Telegram report is not fully configured "
                "(missing bot token or chat id); skipping."
            )
            return

        today = fields.Date.context_today(self)
        this_monday = today - timedelta(days=today.weekday())
        week_start = this_monday - timedelta(days=7)
        week_end = this_monday - timedelta(days=1)
        week_number = week_start.isocalendar()[1]

        orders = self._get_weekly_sales_orders(week_start, week_end)

        pdf_content, dummy = self.env['ir.actions.report']._render_qweb_pdf(
            'sale_daily_report_telegram.action_report_sale_weekly',
            orders.ids,
            data={
                'week_label': 'W%s · %s - %s' % (
                    week_number, week_start.strftime('%d/%m/%Y'), week_end.strftime('%d/%m/%Y')),
            },
        )
        filename = _("Weekly_Sales_Report_W%s_%s.pdf") % (week_number, week_start.strftime('%Y%m%d'))
        caption = self._get_weekly_sales_caption_text(week_number, week_start, week_end, orders)

        service = TelegramService(token)
        for recipient_chat_id in self._split_telegram_chat_ids(chat_id):
            service.send_document(
                chat_id=recipient_chat_id,
                document_content=pdf_content,
                filename=filename,
                caption=caption,
            )

    @api.model
    def _cron_send_daily_sales_report_telegram(self):
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param('sale_daily_report_telegram.enabled', 'True') != 'True':
            return

        chat_id = icp.get_param('sale_daily_report_telegram.chat_id')
        token = icp.get_param('send_by_telegram.bot_token')
        if not chat_id or not token:
            _logger.warning(
                "Daily sales Telegram report is not fully configured "
                "(missing bot token or chat id); skipping."
            )
            return

        report_date = fields.Date.context_today(self)
        orders = self._get_daily_sales_orders(report_date)

        pdf_content, dummy = self.env['ir.actions.report']._render_qweb_pdf(
            'sale_daily_report_telegram.action_report_sale_daily',
            orders.ids,
            data={'report_date': report_date.strftime('%d/%m/%Y')},
        )
        filename = _("Daily_Sales_Report_%s.pdf") % report_date.strftime('%Y%m%d')
        caption = self._get_daily_sales_caption_text(report_date, orders)

        service = TelegramService(token)
        for recipient_chat_id in self._split_telegram_chat_ids(chat_id):
            service.send_document(
                chat_id=recipient_chat_id,
                document_content=pdf_content,
                filename=filename,
                caption=caption,
            )
