# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime, time

import pytz

from odoo import _, api, fields, models

from ..services.telegram_service import TelegramService

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_send_telegram(self):
        """Open wizard to send quotation via Telegram."""
        self.ensure_one()
        
        # Check if partner has Telegram group ID
        if not self.partner_id.telegram_group_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Warning"),
                    'message': _("Customer '%s' does not have a Telegram Group ID configured.") 
                               % self.partner_id.name,
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        return {
            'name': _("Send via Telegram"),
            'type': 'ir.actions.act_window',
            'res_model': 'telegram.message.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': 'sale.order',
                'default_res_id': self.id,
                'default_partner_id': self.partner_id.id,
                'mark_so_as_sent': True,
            }
        }
    
    def _get_telegram_document_name(self):
        """Get PDF document name for Telegram in current language.
        
        Returns:
            str: Localized filename for the PDF
        """
        self.ensure_one()
        # Use context language for translation
        return _("Quotation_%s.pdf") % self.name
    
    def _format_telegram_amount(self, amount):
        """Format a monetary amount with the order's currency symbol."""
        self.ensure_one()
        return "%s %s" % ("{:,.2f}".format(amount), self.currency_id.symbol)

    def _get_telegram_order_lines_text(self):
        """Build the itemized product list (unit, sell price, subtotal).

        Returns:
            str: One line per order line, e.g.
                "1. Product\n    2 Units x 10.00 $ = 20.00 $"
        """
        self.ensure_one()
        lines = self.order_line.filtered(lambda l: not l.display_type)
        return "\n".join(
            "%(index)s. %(product)s\n    %(qty)s %(uom)s x %(price)s = <b>%(subtotal)s</b>"
            % {
                'index': index,
                'product': line.product_id.name,
                'qty': ("%g" % line.product_uom_qty),
                'uom': line.product_uom.name,
                'price': self._format_telegram_amount(line.price_unit),
                'subtotal': self._format_telegram_amount(line.price_subtotal),
            }
            for index, line in enumerate(lines, start=1)
        )

    def _get_telegram_message_text(self):
        """Get message text for Telegram in current language.

        Returns:
            str: Localized message text
        """
        self.ensure_one()
        return _(
    "ជូនចំពោះ %(partner)s,\n\n"
    "Quote តម្លៃរបស់លោកអ្នកត្រូវបានរៀបចំរួចរាល់ហើយ។\n"
    "លេខយោង: <b>%(order)s</b>\n\n"
    "%(lines)s\n\n"
    "សរុប: <b>%(total)s</b>\n\n"
    "សូមពិនិត្យឯកសារ PDF ដែលបានភ្ជាប់មកជាមួយ។\n\n"
    "ដោយក្តីគោរព ពី ABJ Skincare"
      ) % {
    'partner': self.partner_id.name,
    'order': self.name,
    'lines': self._get_telegram_order_lines_text(),
    'total': self._format_telegram_amount(self.amount_total),
     }

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
    def _cron_send_daily_sales_report_telegram(self):
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param('send_by_telegram.sale_daily_report_enabled', 'True') != 'True':
            return

        chat_id = icp.get_param('send_by_telegram.sale_daily_report_chat_id')
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
            'send_by_telegram.action_report_sale_daily',
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
