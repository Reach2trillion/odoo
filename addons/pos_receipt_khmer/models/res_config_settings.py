from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_kh_paper_width = fields.Selection(related='pos_config_id.kh_paper_width', readonly=False)
    pos_kh_raster_dots = fields.Integer(related='pos_config_id.kh_raster_dots', readonly=False)
    # for the "58 mm needs the print logo" warning of the settings view
    # (no 'pos_' prefix: res.config.settings.create would try to copy a 'pos_*' value to a pos.config field)
    kh_pos_has_receipt_logo = fields.Boolean(related='pos_config_id.company_id.kh_has_receipt_logo')
