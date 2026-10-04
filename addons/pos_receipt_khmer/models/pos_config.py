from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    kh_paper_width = fields.Selection(
        [('80', '80 mm'), ('58', '58 mm')], string='Receipt paper width',
        default='80', required=True,
        help='58 mm: narrow receipt layout (raster image 384 dots, or the value below; browser print 48 mm).')
    kh_raster_dots = fields.Integer(
        string='58 mm print width (dots)', default=384,
        help='Width of the printed image on 58 mm paper. 384 for 203-dpi printers (Xprinter, Sunmi, '
             'most ESC/POS units, Epson TM-m10 / TM-m30 58 mm). 360 for Epson TM-T88 in 58 mm mode (180 dpi).')

    @api.constrains('kh_raster_dots')
    def _check_kh_raster_dots(self):
        for config in self:
            # the 58 mm layout is verified from 360 to 384 dots
            if not 360 <= config.kh_raster_dots <= 384:
                raise ValidationError(_('The 58 mm print width must be between 360 and 384 dots.'))

    @api.model
    def _load_pos_data_fields(self, config_id):
        # core loads every pos.config field ([]); only add ours if someone restricted the list
        fields_list = super()._load_pos_data_fields(config_id)
        return fields_list + ['kh_paper_width', 'kh_raster_dots'] if fields_list else fields_list
