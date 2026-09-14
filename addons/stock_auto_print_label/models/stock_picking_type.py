from odoo import api, fields, models

# Report XML ids tried, in order, when picking the default label report.
# The first one is the customer's own 80x100 mm label (if that module is
# installed); the second is the label shipped with this module.
DEFAULT_LABEL_REPORT_XMLIDS = (
    'stock_shipping_label.action_report_shipping_label',
    'stock_auto_print_label.action_report_shipping_label_80x100',
)


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    auto_print_shipping_label = fields.Boolean(
        "Auto Print Shipping Label",
        help="If this checkbox is ticked, Odoo will automatically print the shipping label "
             "(80x100 mm) of a delivery order when it is validated.")
    shipping_label_report_id = fields.Many2one(
        'ir.actions.report', string="Shipping Label Report",
        domain="[('model', '=', 'stock.picking'), ('report_type', '=', 'qweb-pdf')]",
        default=lambda self: self._default_shipping_label_report(),
        help="PDF report used as the shipping label. Any PDF report on Transfers can be used; "
             "the 80x100 mm label shipped with this module is the default.")
    shipping_label_print_mode = fields.Selection([
        ('browser', "Browser print dialog"),
        ('odoo', "Standard Odoo (download / IoT Box / PrintNode)"),
    ], string="Shipping Label Print Mode", default='browser', required=True,
        help="Browser print dialog: the label PDF is generated and the browser's print dialog "
             "opens immediately on the label. Run Chrome with --kiosk-printing to skip the dialog.\n"
             "Standard Odoo: the label goes through Odoo's normal report flow, i.e. a PDF download, "
             "or a direct print if an IoT Box / PrintNode printer is configured on the report.")

    @api.model
    def _default_shipping_label_report(self):
        for xmlid in DEFAULT_LABEL_REPORT_XMLIDS:
            report = self.env.ref(xmlid, raise_if_not_found=False)
            if report and report.exists():
                return report.id
        return False
