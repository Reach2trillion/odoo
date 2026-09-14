from odoo import models
from odoo.addons.web.controllers.utils import clean_action


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_autoprint_report_actions(self):
        """Hook into Odoo's native "print on validation" chain (called at the end
        of ``button_validate``) and append the shipping label report."""
        report_actions = super()._get_autoprint_report_actions()
        pickings = self.filtered(
            lambda p: p.picking_type_id.auto_print_shipping_label
            and p.picking_type_id.shipping_label_report_id
        )
        groups = pickings.grouped(
            lambda p: (p.picking_type_id.shipping_label_report_id, p.picking_type_id.shipping_label_print_mode)
        )
        for (report, print_mode), group in groups.items():
            report = report.with_context(stock_auto_print_label_browser=(print_mode == 'browser'))
            action = report.report_action(group.ids, config=False)
            action = clean_action(action, self.env)
            report_actions.append(action)
        return report_actions

    def get_shipping_label_values(self):
        """Values for the label template that depend on optional modules
        (sale_stock, stock_delivery) so the template never breaks when they
        are not installed."""
        self.ensure_one()
        fields_ = self._fields
        sale = self.sale_id if 'sale_id' in fields_ else None
        carrier = self.carrier_id if 'carrier_id' in fields_ else None
        tracking_ref = self.carrier_tracking_ref if 'carrier_tracking_ref' in fields_ else False
        weight = self.shipping_weight or (self.weight if 'weight' in fields_ else 0.0)
        weight_uom = self.weight_uom_name if 'weight_uom_name' in fields_ else 'kg'
        lines = self.move_ids.filtered(lambda m: m.state != 'cancel' and m.quantity)
        return {
            'order_ref': (sale and sale.name) or self.origin or '',
            'amount_total': sale.amount_total if sale else 0.0,
            'currency': sale.currency_id if sale else self.company_id.currency_id,
            'carrier_name': carrier.name if carrier else '',
            'tracking_ref': tracking_ref or '',
            'weight': weight,
            'weight_uom': weight_uom,
            'lines': lines,
            'total_qty': sum(lines.mapped('quantity')),
        }
