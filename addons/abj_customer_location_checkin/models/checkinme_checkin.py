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

    def _abj_saved_customer_location(self):
        """True when the customer's map location is this check-in position, saved by a visit."""
        self.ensure_one()
        partner = self.partner_id
        return bool(partner and self.has_location and partner.abj_location_source == 'checkin'
                    and abs(partner.partner_latitude - self.latitude) < 1e-7
                    and abs(partner.partner_longitude - self.longitude) < 1e-7)

    def _mobile_vals(self, *args, **kwargs):
        # ABJ phone screen: say so instead of "Verified On Site" (0 m from itself)
        vals = super()._mobile_vals(*args, **kwargs)
        if self._abj_saved_customer_location():
            vals['location_status_label'] = _("Customer location saved")
        return vals

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
        """The phone position becomes the new customer's location, unless the phone is at the
        company / warehouse address (customer created from the office)."""
        office = self.env['res.partner']
        if latitude and longitude:
            office = office._abj_office_near(float(latitude), float(longitude))
        if office:
            latitude = longitude = None
        result = super(CheckinmeCheckin, self.with_context(abj_location_source='checkin')).mobile_create_customer(
            name, phone=phone, street=street, city=city, latitude=latitude, longitude=longitude)
        if office:
            self.env['res.partner'].browse(result['id'])._message_log(body=_(
                "Created from the phone at %(place)s: that position was not saved as the customer's map "
                "location. The first visit at the customer will save it.", place=office.display_name))
        return result
