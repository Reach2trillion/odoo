# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sale_auto_print_enabled = fields.Boolean(
        string="Auto-Print on Confirmation",
        config_parameter='sale_auto_print.enabled',
        help="Automatically open a print-ready page the moment a sale order is confirmed.",
    )
    sale_auto_print_quotation = fields.Boolean(
        string="Include Sales Order / Quotation PDF",
        config_parameter='sale_auto_print.include_quotation',
        default=True,
    )
    sale_auto_print_shipping_label = fields.Boolean(
        string="Include Shipping Label",
        config_parameter='sale_auto_print.include_shipping_label',
        default=True,
    )
    sale_auto_print_label_report_id = fields.Many2one(
        'ir.actions.report',
        string="Shipping Label Report",
        domain=[('model', '=', 'stock.picking')],
        config_parameter='sale_auto_print.label_report_id',
        help="Leave empty to auto-detect (prefers the Shipping Label 100x80 "
             "report from sh_receipt_reports, falls back to stock_shipping_label).",
    )
