from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from .test_partner_location import FAR_AWAY, NEAR_SHOP, SHOP


@tagged('post_install', '-at_install')
class TestPickingLocation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # a delivery person who may process deliveries but not edit contacts
        cls.driver = new_test_user(cls.env, login='abj_driver', groups='stock.group_stock_user')
        cls.customer = cls.env['res.partner'].create({'name': 'Delivery customer'})
        warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], limit=1)
        cls.delivery = cls.env['stock.picking'].create({
            'picking_type_id': warehouse.out_type_id.id,
            'partner_id': cls.customer.id,
        })
        cls.env.company.partner_id.write({'partner_latitude': 0.0, 'partner_longitude': 0.0})

    def test_driver_saves_location_on_arrival(self):
        self.assertFalse(self.customer.with_user(self.driver).has_access('write'))
        delivery = self.delivery.with_user(self.driver)
        self.assertFalse(delivery.abj_partner_has_location)
        result = delivery.abj_action_save_arrival_location(*SHOP, accuracy=9.0)
        self.assertEqual(result['status'], 'saved')
        self.assertAlmostEqual(self.customer.partner_latitude, SHOP[0], places=7)
        self.assertEqual(self.customer.abj_location_source, 'gps')
        self.assertEqual(self.customer.abj_location_user_id, self.driver)
        self.assertTrue(delivery.abj_partner_has_location)
        self.assertIn('destination=11.5563738,104.9282099', delivery.abj_partner_navigate_url)
        self.assertIn('map location of Delivery customer saved', self.delivery.message_ids[0].body)
        partner_note = self.customer.message_ids[0]
        self.assertIn('delivery %s' % self.delivery.name, partner_note.body)
        self.assertEqual(partner_note.author_id, self.driver.partner_id)

    def test_driver_checks_existing_location(self):
        self.customer.write({'abj_location_paste': '11.5563738, 104.9282099'})
        delivery = self.delivery.with_user(self.driver)
        result = delivery.abj_action_save_arrival_location(*NEAR_SHOP, accuracy=9.0)
        self.assertEqual(result['status'], 'same')
        self.assertIn('30 m from the saved map location', self.delivery.message_ids[0].body)
        result = delivery.abj_action_save_arrival_location(*FAR_AWAY, accuracy=9.0)
        self.assertEqual(result['status'], 'confirm')
        self.assertAlmostEqual(self.customer.partner_latitude, SHOP[0], places=7)
        result = delivery.abj_action_save_arrival_location(*FAR_AWAY, accuracy=9.0, force=True)
        self.assertEqual(result['status'], 'saved')
        self.assertAlmostEqual(self.customer.partner_latitude, FAR_AWAY[0], places=7)

    def test_needs_a_delivery_address_and_access(self):
        self.delivery.partner_id = False
        with self.assertRaises(UserError):
            self.delivery.with_user(self.driver).abj_action_save_arrival_location(*SHOP, accuracy=9.0)
        outsider = new_test_user(self.env, login='abj_outsider', groups='base.group_user')
        with self.assertRaises(AccessError):
            self.delivery.with_user(outsider).abj_action_save_arrival_location(*SHOP, accuracy=9.0)
