from odoo.tests import TransactionCase, new_test_user, tagged

SHOP = (11.5563738, 104.9282099)
FAR_AWAY = (11.5770588, 104.9282099)  # 2.3 km north


@tagged('post_install', '-at_install')
class TestCheckinLocation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('checkinme.notify_checkin', 'False')
        cls.seller = new_test_user(
            cls.env, login='abj_seller',
            groups='base.group_user,base.group_partner_manager,sales_team.group_sale_salesman,'
                   'checkinme_sales_activity.group_checkinme_user')
        cls.employee = cls.env['hr.employee'].create({'name': 'Seller', 'user_id': cls.seller.id})
        cls.customer = cls.env['res.partner'].create({'name': 'Visited customer'})
        ActivityType = cls.env['checkinme.activity.type']
        cls.visit = ActivityType.search([('counts_as_visit', '=', True)], limit=1)
        cls.phone_call = ActivityType.search([('counts_as_visit', '=', False)], limit=1)
        cls.env.company.partner_id.write({'partner_latitude': 0.0, 'partner_longitude': 0.0})

    def check_in(self, position=SHOP, accuracy=12.0, activity_type=None):
        return self.env['checkinme.checkin'].with_user(self.seller).create({
            'employee_id': self.employee.id,
            'partner_id': self.customer.id,
            'checkin_type_id': (activity_type or self.visit).id,
            'latitude': position[0],
            'longitude': position[1],
            'accuracy': accuracy,
            'state': 'checked_in',
        })

    def test_visit_saves_missing_location(self):
        checkin = self.check_in()
        self.assertAlmostEqual(self.customer.partner_latitude, SHOP[0], places=7)
        self.assertAlmostEqual(self.customer.partner_longitude, SHOP[1], places=7)
        self.assertEqual(self.customer.abj_location_source, 'checkin')
        self.assertEqual(self.customer.abj_location_user_id, self.seller)
        self.assertEqual(self.customer.abj_location_accuracy, 12.0)
        self.assertIn('visit %s' % checkin.name, self.customer.message_ids[0].body)
        self.assertIn('was saved from this check-in', checkin.message_ids[0].body)
        self.assertEqual(checkin.location_status, 'verified')

    def test_no_location_from_imprecise_gps_or_phone_call(self):
        self.check_in(accuracy=80.0)
        self.assertFalse(self.customer.abj_has_location)
        self.check_in(accuracy=0.0)
        self.assertFalse(self.customer.abj_has_location)
        if self.phone_call:
            self.check_in(activity_type=self.phone_call)
            self.assertFalse(self.customer.abj_has_location)

    def test_no_location_from_the_office(self):
        self.env.company.partner_id.write({'partner_latitude': SHOP[0], 'partner_longitude': SHOP[1]})
        self.check_in()
        self.assertFalse(self.customer.abj_has_location)

    def test_existing_location_is_only_replaced_on_request(self):
        self.customer.write({'abj_location_paste': '11.5563738, 104.9282099'})
        checkin = self.check_in(position=FAR_AWAY)
        self.assertAlmostEqual(self.customer.partner_latitude, SHOP[0], places=7)
        self.assertEqual(checkin.location_status, 'far')
        checkin.with_user(self.seller).action_abj_use_as_customer_location()
        self.assertAlmostEqual(self.customer.partner_latitude, FAR_AWAY[0], places=7)
        self.assertEqual(self.customer.abj_location_source, 'checkin')
        self.assertEqual(checkin.location_status, 'verified')
        self.assertIn('Previous location', self.customer.message_ids[0].body)

    def test_customer_created_from_the_phone(self):
        values = self.env['checkinme.checkin'].with_user(self.seller).mobile_create_customer(
            'Shop created on site', phone='012345678', latitude=SHOP[0], longitude=SHOP[1])
        partner = self.env['res.partner'].browse(values['id'])
        self.assertAlmostEqual(partner.partner_latitude, SHOP[0], places=7)
        self.assertEqual(partner.abj_location_source, 'checkin')
