from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_datetime

from ..tools import location as loc

# Writing one of these without the coordinates makes base_geolocalize reset them to 0, 0.
ADDRESS_FIELDS = ('street', 'zip', 'city', 'state_id', 'country_id')
COORDINATE_FIELDS = ('partner_latitude', 'partner_longitude')
# System parameters "abj_customer_location.<key>" and their defaults.
DEFAULT_PARAMS = {
    # GPS positions less precise than this are refused (taken indoors, or from the phone network)
    'max_accuracy_m': 50,
    # a GPS position this close to the saved location confirms it instead of moving it
    'same_place_m': 100,
    # a GPS position this close to the company / warehouse address is refused (taken at the office)
    'office_radius_m': 150,
}
LOCATION_SOURCES = [
    ('link', 'Map link / coordinates'),
    ('gps', 'Phone GPS on site'),
    ('checkin', 'Sale Check visit'),
    ('address', 'Computed from the address'),
    ('manual', 'Typed in / imported'),
]


def _same_point(first, second):
    return abs(first[0] - second[0]) < 1e-7 and abs(first[1] - second[1]) < 1e-7


def _shorten(text, size):
    """Cut long pasted text (a link has no spaces, so textwrap.shorten would drop it all)."""
    text = ' '.join((text or '').split())
    return text if len(text) <= size else text[:size - 3] + '...'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    abj_location_paste = fields.Char(
        string='Paste map location', compute='_compute_abj_location_paste', inverse='_inverse_abj_location_paste',
        help="Paste the Google Maps link the customer sent (Telegram, Messenger...) or coordinates such as "
             "11.5564, 104.9282. The map location is read from it when you save.")
    abj_location_source = fields.Selection(LOCATION_SOURCES, string='Location source', readonly=True)
    abj_location_accuracy = fields.Float(string='GPS accuracy (m)', readonly=True)
    abj_location_user_id = fields.Many2one('res.users', string='Location saved by', readonly=True)
    abj_location_date = fields.Datetime(string='Location saved on', readonly=True)
    abj_has_location = fields.Boolean(string='Has map location', compute='_compute_abj_location_links')
    abj_location_display = fields.Char(string='Map location', compute='_compute_abj_location_links')
    abj_maps_url = fields.Char(string='Google Maps link', compute='_compute_abj_location_links')
    abj_navigate_url = fields.Char(string='Directions link', compute='_compute_abj_location_links')
    abj_location_info = fields.Char(string='Location saved', compute='_compute_abj_location_info')

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    def _compute_abj_location_paste(self):
        self.abj_location_paste = False

    def _inverse_abj_location_paste(self):
        # The pasted text is read (and removed from the values) in create() / write().
        pass

    @api.depends('partner_latitude', 'partner_longitude', 'abj_location_accuracy')
    def _compute_abj_location_links(self):
        for partner in self:
            latitude, longitude = partner.partner_latitude, partner.partner_longitude
            partner.abj_has_location = bool(latitude or longitude)
            if not partner.abj_has_location:
                partner.abj_location_display = partner.abj_maps_url = partner.abj_navigate_url = False
                continue
            display = loc.format_pair(latitude, longitude)
            if partner.abj_location_accuracy:
                display += ' (±%d m)' % round(partner.abj_location_accuracy)
            partner.abj_location_display = display
            partner.abj_maps_url = loc.maps_url(latitude, longitude)
            partner.abj_navigate_url = loc.directions_url(latitude, longitude)

    @api.depends('abj_location_source', 'abj_location_user_id', 'abj_location_date')
    def _compute_abj_location_info(self):
        """'Phone GPS on site · Nary Rath · 10/26/26 2:05 PM': one text, wraps well on phones."""
        sources = dict(self._fields['abj_location_source']._description_selection(self.env))
        for partner in self:
            parts = [sources.get(partner.abj_location_source), partner.abj_location_user_id.sudo().name]
            if partner.abj_location_date:
                parts.append(format_datetime(self.env, partner.abj_location_date, dt_format='short'))
            info = ' · '.join(part for part in parts if part)
            partner.abj_location_info = info if partner.abj_location_source else False

    @api.onchange('abj_location_paste')
    def _onchange_abj_location_paste(self):
        text = (self.abj_location_paste or '').strip()
        if not text:
            return None
        try:
            found = self._abj_read_location(text)
        except UserError as error:
            return {'warning': {'title': _("Map location not recognised"), 'message': error.args[0]}}
        self.partner_latitude = found.latitude
        self.partner_longitude = found.longitude
        return None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [dict(vals) for vals in vals_list]
        pasted = []
        for vals in vals_list:
            text = (vals.pop('abj_location_paste', None) or '').strip()
            found = self._abj_read_location(text) if text else None
            if found:
                vals.update(self._abj_location_values(found.latitude, found.longitude, 'link'))
            elif ((vals.get('partner_latitude') or vals.get('partner_longitude'))
                    and not vals.get('abj_location_source')):
                self._abj_add_location_metadata(vals)
            pasted.append((text, found))
        partners = super().create(vals_list)
        for partner, (text, found) in zip(partners, pasted, strict=True):
            if partner.partner_latitude or partner.partner_longitude:
                partner._abj_post_location_message(pasted=text, exact=found.exact if found else True)
        return partners

    def write(self, vals):
        vals = dict(vals)
        text = (vals.pop('abj_location_paste', None) or '').strip()
        found = self._abj_read_location(text) if text else None
        if found:
            vals.update(self._abj_location_values(found.latitude, found.longitude, 'link'))
        coordinates_written = any(name in vals for name in COORDINATE_FIELDS)
        if coordinates_written and 'abj_location_source' not in vals:
            self._abj_add_location_metadata(vals)
        address_written = (any(name in vals for name in ADDRESS_FIELDS)
                           and not all(name in vals for name in COORDINATE_FIELDS))
        before = {}
        if coordinates_written or address_written:
            before = {partner.id: (partner.partner_latitude, partner.partner_longitude, partner._abj_address_key())
                      for partner in self}
        result = super().write(vals)
        if address_written:
            self._abj_keep_location(before)
        if coordinates_written:
            for partner in self:
                old = before[partner.id][:2]
                if not _same_point(old, (partner.partner_latitude, partner.partner_longitude)):
                    partner._abj_post_location_message(old=old, pasted=text, exact=found.exact if found else True)
        return result

    def geo_localize(self):
        return super(ResPartner, self.with_context(abj_location_source='address')).geo_localize()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def abj_action_save_gps_location(self, latitude, longitude, accuracy=0.0, force=False):
        """"I'm at this customer" button of the contact form (phone GPS)."""
        self.ensure_one()
        if not self.env.user._is_internal():
            raise AccessError(_("Only employees can save a customer's map location."))
        self.check_access('read')
        return self._abj_save_gps_location(latitude, longitude, accuracy, force=force)

    # ------------------------------------------------------------------
    # Business helpers
    # ------------------------------------------------------------------
    @api.model
    def _abj_location_param(self, key):
        value = self.env['ir.config_parameter'].sudo().get_param('abj_customer_location.%s' % key)
        try:
            return float(value) if value not in (None, False, '') else float(DEFAULT_PARAMS[key])
        except ValueError:
            return float(DEFAULT_PARAMS[key])

    def _abj_location_values(self, latitude, longitude, source, accuracy=0.0):
        """Values saving a map location, with who / how / when it was saved."""
        return {
            'partner_latitude': latitude,
            'partner_longitude': longitude,
            'date_localization': fields.Date.context_today(self),
            'abj_location_source': source,
            'abj_location_accuracy': accuracy or 0.0,
            'abj_location_user_id': self.env.uid,
            'abj_location_date': fields.Datetime.now(),
        }

    def _abj_add_location_metadata(self, vals):
        """Who / how / when for coordinates written by something else than this module: typed in
        the Partner Assignment tab, imported, computed from the address, set by another module."""
        cleared = all(name in vals and not vals[name] for name in COORDINATE_FIELDS)
        if cleared:
            vals.update({
                'abj_location_source': False,
                'abj_location_accuracy': 0.0,
                'abj_location_user_id': False,
                'abj_location_date': False,
            })
            return
        vals.update({
            'abj_location_source': self.env.context.get('abj_location_source') or 'manual',
            'abj_location_accuracy': self.env.context.get('abj_location_accuracy') or 0.0,
            'abj_location_user_id': self.env.uid,
            'abj_location_date': fields.Datetime.now(),
        })
        vals.setdefault('date_localization', fields.Date.context_today(self))

    @api.model
    def _abj_read_location(self, text):
        """Location of pasted text (``tools.location.Location``); UserError explaining what to
        do when nothing usable is found."""
        try:
            found = loc.read_location(text)
        except loc.LocationError as error:
            raise UserError(self._abj_location_error_message(error)) from error
        if not found:
            raise UserError(_(
                "No map location found in “%(text)s”.\n\n"
                "Paste the Google Maps link the customer sent, or coordinates like 11.5564, 104.9282.",
                text=_shorten(text, 120)))
        return found

    @api.model
    def _abj_location_error_message(self, error):
        copy_help = _(
            "Open the link in Google Maps and copy the coordinates of the place: on a computer, "
            "right-click the place and click the numbers at the top; on a phone, touch and hold the "
            "place, the numbers appear in the search box. Then paste them here.")
        if error.code == 'imprecise':
            return _(
                "The coordinates %(value)s are not precise enough: use at least 4 decimals, for example "
                "11.5564, 104.9282 (copy them from Google Maps rather than typing them).",
                value=error.params.get('value'))
        if error.code == 'out_of_range':
            return _(
                "%(value)s is not a place on Earth: the latitude must be between -90 and 90 and the "
                "longitude between -180 and 180.", value=error.params.get('value'))
        if error.code == 'no_location_in_link':
            return _(
                "This link does not show one precise place (it may be a search or a list of places). "
                "Ask the customer to share their location pin, or:\n\n%(help)s", help=copy_help)
        if error.code == 'not_allowed':
            return _("Only Google Maps links are opened automatically.\n\n%(help)s", help=copy_help)
        return _(
            "The link could not be opened (%(reason)s).\n\n%(help)s",
            reason=error.params.get('reason') or _("no answer"), help=copy_help)

    def _abj_address_key(self):
        self.ensure_one()
        return (self.street or '', self.zip or '', self.city or '', self.state_id.id, self.country_id.id)

    def _abj_keep_location(self, before):
        """Standard Odoo (base_geolocalize) resets the map location to 0, 0 whenever the address is
        written without it. The address text rarely finds the place again in Cambodia, so a saved
        location is kept; the chatter says so when the address really changed (the customer may
        have moved)."""
        for partner in self:
            latitude, longitude, address = before[partner.id]
            if not (latitude or longitude):
                continue
            if not (partner.partner_latitude or partner.partner_longitude):
                super(ResPartner, partner).write({'partner_latitude': latitude, 'partner_longitude': longitude})
            if address != partner._abj_address_key():
                partner._message_log(body=_(
                    "The address changed: the map location was kept. If the customer moved, save the new "
                    "location (paste a new map link, or use the GPS button at the new place)."))

    def _abj_save_gps_location(self, latitude, longitude, accuracy=0.0, force=False, origin=''):
        """Save (or check) the map location with a phone GPS position.

        Returns a dict for the GPS button: ``status`` is one of
        saved, same (already saved there), confirm (far from the saved location: call again with
        force=True to replace it), inaccurate (GPS not precise enough), office (taken at the
        company / warehouse address).
        """
        self.ensure_one()
        try:
            position = loc.make_location(latitude, longitude)
            accuracy = float(accuracy or 0.0)
        except (TypeError, ValueError, loc.LocationError):
            position = None
        if not position:
            raise UserError(_("The phone sent an invalid GPS position. Please try again."))
        max_accuracy = self._abj_location_param('max_accuracy_m')
        if accuracy <= 0 or accuracy > max_accuracy:
            return {'status': 'inaccurate', 'accuracy': round(accuracy), 'max_accuracy': round(max_accuracy)}
        office = self._abj_office_near(position.latitude, position.longitude)
        if office:
            return {'status': 'office', 'place': office.display_name}
        result = {'partner': self.display_name, 'accuracy': round(accuracy)}
        if self.partner_latitude or self.partner_longitude:
            distance = loc.distance_m(position.latitude, position.longitude,
                                      self.partner_latitude, self.partner_longitude)
            result.update(distance=round(distance), distance_label=self._abj_format_distance(distance))
            if distance <= self._abj_location_param('same_place_m'):
                return dict(result, status='same')
            if not force:
                return dict(result, status='confirm')
            result['replaced'] = True
        self.sudo().with_context(abj_location_note=origin).write(
            self._abj_location_values(position.latitude, position.longitude, 'gps', accuracy))
        return dict(result, status='saved')

    def _abj_office_near(self, latitude, longitude):
        """The company or warehouse address the position is at, if any: a position saved from the
        office would send the next delivery back to the office."""
        radius = self._abj_location_param('office_radius_m')
        if radius <= 0:
            return self.browse()
        places = self.env['res.company'].sudo().search([]).partner_id
        places |= self.env['stock.warehouse'].sudo().search([]).partner_id
        for place in places - self:
            if (place.partner_latitude or place.partner_longitude) and loc.distance_m(
                    latitude, longitude, place.partner_latitude, place.partner_longitude) <= radius:
                return place
        return self.browse()

    @api.model
    def _abj_format_distance(self, meters):
        if meters < 1000:
            return _("%(meters)s m", meters=int(round(meters)))
        return _("%(kilometers)s km", kilometers='%.1f' % (meters / 1000.0))

    @api.model
    def _abj_map_link(self, latitude, longitude):
        return Markup('<a href="%s" target="_blank" rel="noopener">%s</a>') % (
            loc.maps_url(latitude, longitude), loc.format_pair(latitude, longitude))

    def _abj_post_location_message(self, old=None, pasted='', exact=True):
        """Chatter note telling who saved which location, how, and what it replaced."""
        self.ensure_one()
        latitude, longitude = self.partner_latitude, self.partner_longitude
        had_old = bool(old and (old[0] or old[1]))
        if not (latitude or longitude):
            if had_old:
                self._message_log(body=Markup('📍 %s %s') % (
                    _("Map location removed. It was:"), self._abj_map_link(*old)))
            return
        sources = dict(self._fields['abj_location_source']._description_selection(self.env))
        lines = [Markup('📍 <b>%s</b> %s') % (_("Map location saved:"), self._abj_map_link(latitude, longitude))]
        details = sources.get(self.abj_location_source) or ''
        if self.abj_location_accuracy:
            details += ' (±%d m)' % round(self.abj_location_accuracy)
        note = self.env.context.get('abj_location_note')
        if note:
            details = '%s - %s' % (details, note) if details else note
        if details:
            lines.append(Markup('%s %s') % (_("Source:"), details))
        if not exact:
            lines.append(_("The link only showed a map, not a pinned place: check the location is right."))
        if had_old:
            distance = loc.distance_m(old[0], old[1], latitude, longitude)
            lines.append(Markup('%s %s (%s)') % (
                _("Previous location:"), self._abj_map_link(*old),
                _("%(distance)s away", distance=self._abj_format_distance(distance))))
        if pasted:
            lines.append(Markup('%s <i>%s</i>') % (_("Pasted:"), _shorten(pasted, 300)))
        self._message_log(body=Markup('<br/>').join(lines))
