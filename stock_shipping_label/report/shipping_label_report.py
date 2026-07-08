# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models


class ShippingLabelReport(models.AbstractModel):
    _name = 'report.stock_shipping_label.report_shipping_label_document'
    _description = "Shipping Label (PDF)"

    def _get_report_values(self, docids, data=None):
        docs = self.env['stock.picking'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'stock.picking',
            'docs': docs,
            'thanks_en': _("Thank You For Your Order!"),
            'thanks_km': "សូមអរគុណសម្រាប់ការទិញឥវ៉ាន់របស់អ្នក!",
        }
