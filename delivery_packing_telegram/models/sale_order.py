# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from html import escape

from odoo import models

from odoo.addons.send_by_telegram.services.telegram_service import TelegramService

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super().action_confirm()
        self._notify_telegram_packing()
        return res

    def _notify_telegram_packing(self):
        icp = self.env['ir.config_parameter'].sudo()
        token = icp.get_param('send_by_telegram.bot_token')
        if not token:
            return
        default_group_id = icp.get_param('delivery_packing_telegram.default_group_id')

        service = None
        for order in self:
            pickings = order.picking_ids.filtered(
                lambda p: p.picking_type_id.code == 'outgoing' and p.state != 'cancel')
            for picking in pickings:
                group_id = picking.picking_type_id.telegram_group_id or default_group_id
                if not group_id:
                    continue
                message = order._build_telegram_packing_message(picking)
                if service is None:
                    service = TelegramService(token)
                try:
                    service.send_message(group_id, message)
                except Exception:
                    _logger.exception(
                        "Failed to send Telegram packing notification for %s", picking.name)

    def _build_telegram_packing_message(self, picking):
        self.ensure_one()
        moves = picking.move_ids.filtered(lambda m: m.state != 'cancel')

        lines = []
        for move in moves:
            qty = '%g' % move.product_uom_qty
            lines.append("• %s x %s %s" % (
                escape(move.product_id.display_name),
                qty,
                escape(move.product_uom.name),
            ))

        total_qty = '%g' % sum(moves.mapped('product_uom_qty'))

        parts = [
            "📦 <b>New Packing Request</b>",
            "Operation: <b>%s</b>" % escape(picking.picking_type_id.display_name),
            "Order: <b>%s</b>" % escape(self.name),
            "Customer: <b>%s</b>" % escape(self.partner_id.name or ''),
            "Delivery: <b>%s</b>" % escape(picking.name),
            "",
            "<b>Products to pack:</b>",
        ]
        parts.extend(lines)
        parts.append("")
        parts.append("<b>Total Qty:</b> %s" % total_qty)
        return "\n".join(parts)
