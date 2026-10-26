from odoo import _, api, models
from odoo.exceptions import UserError


class CheckinmeCheckin(models.Model):
    _inherit = 'checkinme.checkin'

    def _on_checked_in(self):
        result = super()._on_checked_in()
        self._abj_fill_customer_location()
        return result

    def _abj_fill_customer_location(self):
        """A visit at a customer without a map location saves it. Never moves an existing
        location (a visit can happen elsewhere: a café, the market): that needs the button."""
        Partner = self.env['res.partner']
        max_accuracy = Partner._abj_location_param('max_accuracy_m')
        for checkin in self:
            partner = checkin.partner_id
            if (not partner or not checkin.has_location or not checkin.counts_as_visit
                    or partner.partner_latitude or partner.partner_longitude
                    or not 0 < checkin.accuracy <= max_accuracy
                    or partner._abj_office_near(checkin.latitude, checkin.longitude)):
                continue
            checkin._abj_save_customer_location()

    def _abj_save_customer_location(self):
        self.ensure_one()
        partner = self.partner_id
        partner.sudo().with_context(abj_location_note=_("visit %(checkin)s", checkin=self.name)).write(
            partner._abj_location_values(self.latitude, self.longitude, 'checkin', self.accuracy))
        self._message_log(body=_("📍 The map location of %(partner)s was saved from this check-in.",
                                 partner=partner.display_name))

    def action_abj_use_as_customer_location(self):
        """Save this check-in position as the customer's map location (replaces the saved one)."""
        self.ensure_one()
        self.check_access('write')
        if not self.partner_id:
            raise UserError(_("Select the customer first."))
        if not self.has_location:
            raise UserError(_("This check-in has no GPS position."))
        self._abj_save_customer_location()
        return True

    @api.model
    def mobile_create_customer(self, name, phone='', street='', city='', latitude=None, longitude=None):
        return super(CheckinmeCheckin, self.with_context(abj_location_source='checkin')).mobile_create_customer(
            name, phone=phone, street=street, city=city, latitude=latitude, longitude=longitude)
