# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging

from odoo import models
from odoo.tools.pdf import merge_pdf

_logger = logging.getLogger(__name__)

TRUE_VALUES = ('1', 'true', 'True')

# Tried in order until one resolves to an installed report.
FALLBACK_LABEL_REPORT_XMLIDS = (
    'sh_receipt_reports.action_sh_rr_delivery_80x100_report',
    'stock_shipping_label.action_report_shipping_label',
)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super().action_confirm()
        if len(self) != 1:
            return res
        action = self._get_auto_print_action()
        return action or res

    def _get_auto_print_action(self):
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param('sale_auto_print.enabled') not in TRUE_VALUES:
            return False

        pdf_parts = []

        if icp.get_param('sale_auto_print.include_quotation', 'True') in TRUE_VALUES:
            so_report = self.env.ref('sale.action_report_saleorder', raise_if_not_found=False)
            if so_report:
                pdf, _ext = self.env['ir.actions.report']._render_qweb_pdf(
                    so_report.report_name, self.ids)
                pdf_parts.append(pdf)
            else:
                _logger.warning("Auto-Print: sale.action_report_saleorder not found.")

        if icp.get_param('sale_auto_print.include_shipping_label', 'True') in TRUE_VALUES:
            label_report = self._get_auto_print_label_report()
            pickings = self.picking_ids.filtered(
                lambda p: p.picking_type_id.code == 'outgoing' and p.state != 'cancel')
            if label_report and pickings:
                pdf, _ext = self.env['ir.actions.report']._render_qweb_pdf(
                    label_report.report_name, pickings.ids)
                pdf_parts.append(pdf)
            elif not label_report:
                _logger.warning("Auto-Print: no shipping label report configured/found.")

        if not pdf_parts:
            return False

        combined = pdf_parts[0] if len(pdf_parts) == 1 else merge_pdf(pdf_parts)

        attachment = self.env['ir.attachment'].create({
            'name': 'AutoPrint-%s.pdf' % self.name,
            'type': 'binary',
            'datas': base64.b64encode(combined),
            'res_model': 'sale.order',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/sale_auto_print/print/%s' % attachment.id,
            'target': 'new',
        }

    def _get_auto_print_label_report(self):
        icp = self.env['ir.config_parameter'].sudo()
        report_id = icp.get_param('sale_auto_print.label_report_id')
        if report_id:
            report = self.env['ir.actions.report'].browse(int(report_id)).exists()
            if report:
                return report

        for xmlid in FALLBACK_LABEL_REPORT_XMLIDS:
            report = self.env.ref(xmlid, raise_if_not_found=False)
            if report:
                return report
        return False
