from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, TransactionCase, new_test_user, tagged

from ..tools import location as loc
from .test_location_parser import ANDROID_PAGE, ANDROID_TARGET, FakeGoogle

# A customer in Phnom Penh, a point 30 m north of it and one 2.3 km north.
SHOP = (11.5563738, 104.9282099)
NEAR_SHOP = (11.5566438, 104.9282099)
FAR_AWAY = (11.5770588, 104.9282099)


@tagged('post_install', '-at_install')
class TestPartnerLocation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.office_user = new_test_user(
            cls.env, login='abj_office', groups='base.group_user,base.group_partner_manager')
        cls.customer = cls.env['res.partner'].create({'name': 'Bong Srey Shop', 'city': 'Phnom Penh'})
        cls.company_partner = cls.env.company.partner_id
        cls.company_partner.write({'partner_latitude': 0.0, 'partner_longitude': 0.0})

    def setUp(self):
        super().setUp()
        loc._cache.clear()

    def last_note(self, record):
        return record.message_ids[:1].body or ''

    def test_paste_coordinates(self):
        customer = self.customer.with_user(self.office_user)
        customer.write({'abj_location_paste': '11.5563738, 104.9282099'})
        self.assertAlmostEqual(customer.partner_latitude, SHOP[0], places=7)
        self.assertAlmostEqual(customer.partner_longitude, SHOP[1], places=7)
        self.assertEqual(customer.abj_location_source, 'link')
        self.assertEqual(customer.abj_location_user_id, self.office_user)
        self.assertTrue(customer.abj_location_date)
        self.assertTrue(customer.date_localization)
        self.assertTrue(customer.abj_has_location)
        self.assertEqual(customer.abj_location_display, '11.5563738, 104.9282099')
        self.assertIn('query=11.5563738,104.9282099', customer.abj_maps_url)
        self.assertIn('destination=11.5563738,104.9282099', customer.abj_navigate_url)
        self.assertTrue(customer.abj_location_info.startswith('Map link / coordinates · %s · ' % self.office_user.name))
        note = self.last_note(customer)
        self.assertIn('Map location saved', note)
        self.assertIn('11.5563738, 104.9282099', note)
        self.assertIn('Map link / coordinates', note)

    def test_paste_google_link_on_create(self):
        partner = self.env['res.partner'].create({
            'name': 'New customer from Telegram',
            'abj_location_paste': 'https://maps.google.com/maps?q=11.5563738,104.9282099&z=16',
        })
        self.assertAlmostEqual(partner.partner_latitude, SHOP[0], places=7)
        self.assertEqual(partner.abj_location_source, 'link')
        self.assertIn('maps.google.com/maps?q=11.5563738', self.last_note(partner))

    def test_paste_short_link(self):
        google = FakeGoogle({
            'https://maps.app.goo.gl/': (302, ANDROID_TARGET, ''),
            'https://www.google.com/maps/place/': (200, None, ANDROID_PAGE),
        })
        with patch.object(loc, 'http_fetch', google):
            self.customer.abj_location_paste = 'https://maps.app.goo.gl/PJdcARfqULFnpENj7?g_st=it'
        self.assertAlmostEqual(self.customer.partner_latitude, 52.5162746, places=7)
        self.assertAlmostEqual(self.customer.partner_longitude, 13.3777041, places=7)

    def test_paste_unreadable(self):
        with self.assertRaisesRegex(UserError, 'No map location found'):
            self.customer.write({'abj_location_paste': 'near the market'})
        with self.assertRaisesRegex(UserError, 'not precise enough'):
            self.customer.write({'abj_location_paste': '11.55, 104.92'})
        google = FakeGoogle({'https://maps.app.goo.gl/': (404, None, '')})
        with patch.object(loc, 'http_fetch', google), self.assertRaisesRegex(UserError, 'could not be opened'):
            self.customer.write({'abj_location_paste': 'https://maps.app.goo.gl/Dead'})
        self.assertFalse(self.customer.abj_has_location)

    def test_form_preview(self):
        """Pasting fills the coordinates in the form at once; saving keeps them."""
        with Form(self.customer.with_user(self.office_user)) as form:
            form.abj_location_paste = '11.5563738, 104.9282099'
            self.assertAlmostEqual(form.partner_latitude, SHOP[0], places=7)
            self.assertEqual(form.abj_location_display, '11.5563738, 104.9282099')
        self.assertAlmostEqual(self.customer.partner_longitude, SHOP[1], places=7)
        self.assertEqual(self.customer.abj_location_source, 'link')
        self.assertFalse(self.customer.abj_location_paste)

    def test_child_delivery_address(self):
        """A delivery address of the customer gets its own location from the Contacts & Addresses tab."""
        with Form(self.customer) as form:
            with form.child_ids.new() as address:
                address.type = 'delivery'
                address.name = 'Warehouse of Bong Srey'
                address.abj_location_paste = '11.5566438, 104.9282099'
        address = self.customer.child_ids
        self.assertAlmostEqual(address.partner_latitude, NEAR_SHOP[0], places=7)
        self.assertFalse(self.customer.abj_has_location)

    def test_address_change_keeps_location(self):
        """Standard Odoo erases the location when the address is written; ours is kept."""
        self.customer.abj_location_paste = '11.5563738, 104.9282099'
        notes = len(self.customer.message_ids)
        self.customer.write({'street': 'Street 271, house 12', 'city': 'Phnom Penh'})
        self.assertAlmostEqual(self.customer.partner_latitude, SHOP[0], places=7)
        self.assertAlmostEqual(self.customer.partner_longitude, SHOP[1], places=7)
        self.assertEqual(len(self.customer.message_ids), notes + 1)
        self.assertIn('The address changed: the map location was kept', self.last_note(self.customer))
        # the same address written again (e.g. by an order form): kept, no new note
        self.customer.write({'street': 'Street 271, house 12'})
        self.assertAlmostEqual(self.customer.partner_latitude, SHOP[0], places=7)
        self.assertEqual(len(self.customer.message_ids), notes + 1)

    def test_typed_and_cleared_coordinates(self):
        self.customer.write({'partner_latitude': SHOP[0], 'partner_longitude': SHOP[1]})
        self.assertEqual(self.customer.abj_location_source, 'manual')
        self.customer.write({'partner_latitude': 0.0, 'partner_longitude': 0.0})
        self.assertFalse(self.customer.abj_location_source)
        self.assertFalse(self.customer.abj_location_user_id)
        self.assertIn('Map location removed', self.last_note(self.customer))

    def test_computed_from_address(self):
        Partner = type(self.env['res.partner'])
        with patch.object(Partner, '_geo_localize', return_value=SHOP):
            self.customer.with_context(force_geo_localize=True).geo_localize()
        self.assertAlmostEqual(self.customer.partner_latitude, SHOP[0], places=7)
        self.assertEqual(self.customer.abj_location_source, 'address')

    def test_gps_saves_missing_location(self):
        customer = self.customer.with_user(self.office_user)
        result = customer.abj_action_save_gps_location(*SHOP, accuracy=12.4)
        self.assertEqual(result['status'], 'saved')
        self.assertFalse(result.get('replaced'))
        self.assertAlmostEqual(customer.partner_latitude, SHOP[0], places=7)
        self.assertEqual(customer.abj_location_source, 'gps')
        self.assertEqual(customer.abj_location_accuracy, 12.4)
        self.assertEqual(customer.abj_location_display, '11.5563738, 104.9282099 (±12 m)')
        self.assertIn('Phone GPS on site (±12 m)', self.last_note(customer))

    def test_gps_refuses_imprecise_positions(self):
        for accuracy in (0.0, 80.0):
            result = self.customer.abj_action_save_gps_location(*SHOP, accuracy=accuracy)
            self.assertEqual(result['status'], 'inaccurate')
        self.assertFalse(self.customer.abj_has_location)
        self.env['ir.config_parameter'].sudo().set_param('abj_customer_location.max_accuracy_m', '100')
        result = self.customer.abj_action_save_gps_location(*SHOP, accuracy=80.0)
        self.assertEqual(result['status'], 'saved')

    def test_gps_refuses_the_office(self):
        self.company_partner.write({'partner_latitude': SHOP[0], 'partner_longitude': SHOP[1]})
        result = self.customer.abj_action_save_gps_location(*NEAR_SHOP, accuracy=10)
        self.assertEqual(result['status'], 'office')
        self.assertEqual(result['place'], self.company_partner.display_name)
        self.assertFalse(self.customer.abj_has_location)
        # the company itself can be located from the office
        result = self.company_partner.abj_action_save_gps_location(*NEAR_SHOP, accuracy=10)
        self.assertEqual(result['status'], 'same')

    def test_gps_checks_and_replaces_existing_location(self):
        self.customer.abj_location_paste = '11.5563738, 104.9282099'
        # 30 m away: the saved location is right, nothing changes
        result = self.customer.abj_action_save_gps_location(*NEAR_SHOP, accuracy=10)
        self.assertEqual(result['status'], 'same')
        self.assertEqual(result['distance'], 30)
        self.assertEqual(self.customer.abj_location_source, 'link')
        # 2.3 km away: ask first
        result = self.customer.abj_action_save_gps_location(*FAR_AWAY, accuracy=10)
        self.assertEqual(result['status'], 'confirm')
        self.assertEqual(result['distance_label'], '2.3 km')
        self.assertAlmostEqual(self.customer.partner_latitude, SHOP[0], places=7)
        # confirmed: replaced, the previous location stays in the chatter
        result = self.customer.abj_action_save_gps_location(*FAR_AWAY, accuracy=10, force=True)
        self.assertEqual(result['status'], 'saved')
        self.assertTrue(result['replaced'])
        self.assertAlmostEqual(self.customer.partner_latitude, FAR_AWAY[0], places=7)
        note = self.last_note(self.customer)
        self.assertIn('Previous location', note)
        self.assertIn('11.5563738, 104.9282099', note)

    def test_gps_rejects_bad_input_and_outsiders(self):
        with self.assertRaises(UserError):
            self.customer.abj_action_save_gps_location('abc', 104.9, accuracy=10)
        with self.assertRaises(UserError):
            self.customer.abj_action_save_gps_location(95.0, 104.9, accuracy=10)
        portal = new_test_user(self.env, login='abj_portal', groups='base.group_portal')
        with self.assertRaises(AccessError):
            portal.partner_id.with_user(portal).abj_action_save_gps_location(*SHOP, accuracy=10)

    def test_search_filters(self):
        self.customer.abj_location_paste = '11.5563738, 104.9282099'
        other = self.env['res.partner'].create({'name': 'Never located'})
        without = self.env['res.partner'].search(
            [('id', 'in', (self.customer | other).ids), ('partner_latitude', '=', 0), ('partner_longitude', '=', 0)])
        self.assertEqual(without, other)
