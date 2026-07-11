# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models

from odoo.addons.send_by_telegram.services.telegram_service import TelegramService

_logger = logging.getLogger(__name__)


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    @api.model
    def _get_stock_report_tz(self):
        tz_name = self.env.company.partner_id.tz or self.env.user.tz or 'UTC'
        return pytz.timezone(tz_name)

    @api.model
    def _get_stock_report_locations(self):
        icp = self.env['ir.config_parameter'].sudo()
        location_ids = []
        for param in ('stock_report_telegram.location_1_id', 'stock_report_telegram.location_2_id'):
            value = icp.get_param(param)
            if value:
                location_ids.append(int(value))
        return self.env['stock.location'].browse(location_ids).exists()

    @api.model
    def _get_stock_on_hand(self, locations):
        """Return {product: {location: qty}} on-hand quantities in `locations`."""
        quants = self.search([('location_id', 'in', locations.ids)])
        data = defaultdict(lambda: defaultdict(float))
        for quant in quants:
            data[quant.product_id][quant.location_id] += quant.quantity
        return data

    @staticmethod
    def _split_telegram_chat_ids(chat_id):
        """Allow a comma-separated list of chat IDs (e.g. one per boss)."""
        return [part.strip() for part in (chat_id or '').split(',') if part.strip()]

    @staticmethod
    def _get_move_line_done_qty(move_line):
        for fname in ('quantity', 'qty_done'):
            if fname in move_line._fields:
                return move_line[fname]
        return 0.0

    @api.model
    def _get_stock_sold_between(self, date_from, date_to, locations):
        """{product: qty} that left `locations` to a customer between date_from/date_to (UTC, naive)."""
        move_lines = self.env['stock.move.line'].search([
            ('location_id', 'in', locations.ids),
            ('location_dest_id.usage', '=', 'customer'),
            ('state', '=', 'done'),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ])
        data = defaultdict(float)
        for line in move_lines:
            data[line.product_id] += self._get_move_line_done_qty(line)
        return data

    @api.model
    def _cron_send_daily_stock_report_telegram(self):
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param('stock_report_telegram.enabled', 'True') != 'True':
            return

        chat_id = icp.get_param('stock_report_telegram.chat_id')
        token = icp.get_param('send_by_telegram.bot_token')
        if not chat_id or not token:
            _logger.warning(
                "Daily stock Telegram report is not fully configured "
                "(missing bot token or chat id); skipping."
            )
            return

        locations = self._get_stock_report_locations()
        if not locations:
            _logger.warning(
                "Daily stock Telegram report has no locations configured; skipping."
            )
            return

        tz = self._get_stock_report_tz()
        report_date = fields.Date.context_today(self)
        day_start_utc = tz.localize(datetime.combine(report_date, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        day_end_utc = tz.localize(datetime.combine(report_date, time.max)).astimezone(pytz.UTC).replace(tzinfo=None)

        pdf_content, dummy = self.env['ir.actions.report']._render_qweb_pdf(
            'stock_report_telegram.action_report_stock_daily',
            [],
            data={
                'report_date': report_date.strftime('%d/%m/%Y'),
                'date_from': day_start_utc,
                'date_to': day_end_utc,
            },
        )
        filename = _("Daily_Stock_Report_%s.pdf") % report_date.strftime('%Y%m%d')
        caption = _(
            "📦 Daily Stock Report / របាយការណ៍ស្តុកប្រចាំថ្ងៃ / 每日库存报告\n%s"
        ) % report_date.strftime('%d/%m/%Y')
        service = TelegramService(token)
        for recipient_chat_id in self._split_telegram_chat_ids(chat_id):
            service.send_document(
                chat_id=recipient_chat_id,
                document_content=pdf_content,
                filename=filename,
                caption=caption,
            )

    @api.model
    def _cron_send_weekly_stock_report_telegram(self):
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param('stock_report_telegram.weekly_enabled', 'True') != 'True':
            return

        chat_id = icp.get_param('stock_report_telegram.chat_id')
        token = icp.get_param('send_by_telegram.bot_token')
        if not chat_id or not token:
            _logger.warning(
                "Weekly stock Telegram report is not fully configured "
                "(missing bot token or chat id); skipping."
            )
            return

        locations = self._get_stock_report_locations()
        if not locations:
            _logger.warning(
                "Weekly stock Telegram report has no locations configured; skipping."
            )
            return

        tz = self._get_stock_report_tz()
        today = fields.Date.context_today(self)
        this_monday = today - timedelta(days=today.weekday())
        week_start = this_monday - timedelta(days=7)
        week_end = this_monday - timedelta(days=1)

        week_start_utc = tz.localize(datetime.combine(week_start, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        week_end_utc = tz.localize(datetime.combine(week_end, time.max)).astimezone(pytz.UTC).replace(tzinfo=None)

        pdf_content, dummy = self.env['ir.actions.report']._render_qweb_pdf(
            'stock_report_telegram.action_report_stock_weekly',
            [],
            data={
                'week_label': '%s - %s' % (week_start.strftime('%d/%m/%Y'), week_end.strftime('%d/%m/%Y')),
                'date_from': week_start_utc,
                'date_to': week_end_utc,
            },
        )
        filename = _("Weekly_Stock_Report_%s.pdf") % week_start.strftime('%Y%m%d')
        caption = _(
            "📦 Weekly Stock Report / របាយការណ៍ស្តុកប្រចាំសប្តាហ៍\n%s - %s"
        ) % (week_start.strftime('%d/%m/%Y'), week_end.strftime('%d/%m/%Y'))
        service = TelegramService(token)
        for recipient_chat_id in self._split_telegram_chat_ids(chat_id):
            service.send_document(
                chat_id=recipient_chat_id,
                document_content=pdf_content,
                filename=filename,
                caption=caption,
            )

    @api.model
    def _cron_send_monthly_stock_report_telegram(self):
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param('stock_report_telegram.monthly_enabled', 'True') != 'True':
            return

        chat_id = icp.get_param('stock_report_telegram.chat_id')
        token = icp.get_param('send_by_telegram.bot_token')
        if not chat_id or not token:
            _logger.warning(
                "Monthly stock Telegram report is not fully configured "
                "(missing bot token or chat id); skipping."
            )
            return

        locations = self._get_stock_report_locations()
        if not locations:
            _logger.warning(
                "Monthly stock Telegram report has no locations configured; skipping."
            )
            return

        tz = self._get_stock_report_tz()
        today = fields.Date.context_today(self)
        first_of_this_month = today.replace(day=1)
        month_end = first_of_this_month - timedelta(days=1)
        month_start = month_end.replace(day=1)

        month_start_utc = tz.localize(datetime.combine(month_start, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        month_end_utc = tz.localize(datetime.combine(month_end, time.max)).astimezone(pytz.UTC).replace(tzinfo=None)

        pdf_content, dummy = self.env['ir.actions.report']._render_qweb_pdf(
            'stock_report_telegram.action_report_stock_monthly',
            [],
            data={
                'month_label': month_start.strftime('%B %Y'),
                'date_from': month_start_utc,
                'date_to': month_end_utc,
            },
        )
        filename = _("Monthly_Stock_Report_%s.pdf") % month_start.strftime('%Y%m')
        caption = _(
            "📦 Monthly Stock Report / របាយការណ៍ស្តុកប្រចាំខែ / 每月库存报告\n%s"
        ) % month_start.strftime('%B %Y')
        service = TelegramService(token)
        for recipient_chat_id in self._split_telegram_chat_ids(chat_id):
            service.send_document(
                chat_id=recipient_chat_id,
                document_content=pdf_content,
                filename=filename,
                caption=caption,
            )
