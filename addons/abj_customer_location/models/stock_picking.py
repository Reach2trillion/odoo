from markupsafe import Markup

from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    abj_partner_has_location = fields.Boolean(
        related='partner_id.abj_has_location', string='Customer has a map location')
    abj_partner_navigate_url = fields.Char(
        related='partner_id.abj_navigate_url', string='Directions to the customer')

    def abj_action_save_arrival_location(self, latitude, longitude, accuracy=0.0, force=False):
        """"I'm here" button of a delivery: save, or check, the map location of the delivery
        address with the phone GPS. The delivery person does not need the right to edit contacts."""
        self.ensure_one()
        self.check_access('write')
        partner = self.partner_id
        if not partner:
            raise UserError(_("Set the delivery address of %(picking)s first.", picking=self.name))
        result = partner._abj_save_gps_location(
            latitude, longitude, accuracy, force=force, origin=_("delivery %(picking)s", picking=self.name))
        if result['status'] == 'saved':
            message = _("Arrived at the customer: map location of %(partner)s saved.", partner=partner.display_name)
        elif result['status'] == 'same':
            message = _("Arrived at the customer, %(distance)s from the saved map location.",
                        distance=result['distance_label'])
        else:
            return result
        Partner = self.env['res.partner']
        self._message_log(body=Markup('📍 %s %s (±%d m)') % (
            message, Partner._abj_map_link(float(latitude), float(longitude)), round(float(accuracy))))
        return result
