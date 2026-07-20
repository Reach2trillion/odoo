# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models


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
        """Build a compact, easy-to-read product list: one line per product.

        Returns:
            str: e.g. "• ABJ-Mask — 2 x 3.00 $ = 6.00 $"
        """
        self.ensure_one()
        lines = self.order_line.filtered(lambda l: not l.display_type)
        return "\n".join(
            "• %(product)s — %(qty)s x %(price)s = <b>%(subtotal)s</b>"
            % {
                'product': line.product_id.name,
                'qty': ("%g" % line.product_uom_qty),
                'price': self._format_telegram_amount(line.price_unit),
                'subtotal': self._format_telegram_amount(line.price_subtotal),
            }
            for line in lines
        )

    def _get_telegram_message_text(self):
        """Get message text for Telegram in current language.

        Returns:
            str: Localized message text
        """
        self.ensure_one()
        return _(
    "ជូនចំពោះ %(partner)s 💜\n\n"
    "🧾 Quote លេខ: <b>%(order)s</b>\n\n"
    "%(lines)s\n\n"
    "💰 សរុប: <b>%(total)s</b>\n\n"
    "📎 PDF ភ្ជាប់មកជាមួយ\n"
    "អរគុណ ពី ABJ Skincare 💜"
      ) % {
    'partner': self.partner_id.name,
    'order': self.name,
    'lines': self._get_telegram_order_lines_text(),
    'total': self._format_telegram_amount(self.amount_total),
     }
