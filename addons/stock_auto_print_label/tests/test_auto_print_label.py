from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAutoPrintLabel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], limit=1)
        cls.delivery_type = cls.warehouse.out_type_id
        cls.label_report = cls.env.ref('stock_auto_print_label.action_report_shipping_label_80x100')
        cls.partner = cls.env['res.partner'].create({
            'name': 'Label Customer',
            'phone': '+855 12 345 678',
            'street': 'Street 271',
            'city': 'Phnom Penh',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Label Test Product',
            'type': 'consu',
            'is_storable': True,
        })
        cls.env['stock.quant']._update_available_quantity(cls.product, cls.warehouse.lot_stock_id, 10)

    def _create_delivery(self):
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.delivery_type.id,
            'partner_id': self.partner.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'move_ids': [(0, 0, {
                'name': self.product.name,
                'product_id': self.product.id,
                'product_uom_qty': 2,
                'product_uom': self.product.uom_id.id,
                'location_id': self.warehouse.lot_stock_id.id,
                'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.quantity = 2
        return picking

    def test_post_init_hook_enabled_delivery_types(self):
        self.assertTrue(self.delivery_type.auto_print_shipping_label)
        self.assertTrue(self.delivery_type.shipping_label_report_id)
        self.assertEqual(self.delivery_type.shipping_label_report_id.model, 'stock.picking')

    def test_validate_returns_label_print_action_browser_mode(self):
        self.delivery_type.write({
            'auto_print_shipping_label': True,
            'auto_print_delivery_slip': False,
            'shipping_label_report_id': self.label_report.id,
            'shipping_label_print_mode': 'browser',
        })
        picking = self._create_delivery()
        action = picking.button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertEqual(action['type'], 'ir.actions.client')
        self.assertEqual(action['tag'], 'do_multi_print')
        reports = action['params']['reports']
        self.assertEqual(len(reports), 1)
        report = reports[0]
        self.assertEqual(report['type'], 'ir.actions.report')
        self.assertEqual(report['report_name'], self.label_report.report_name)
        self.assertEqual(report['context']['active_ids'], picking.ids)
        self.assertTrue(report['context']['stock_auto_print_label_browser'])

    def test_validate_odoo_mode_keeps_delivery_slip_and_adds_label(self):
        self.delivery_type.write({
            'auto_print_shipping_label': True,
            'auto_print_delivery_slip': True,
            'shipping_label_report_id': self.label_report.id,
            'shipping_label_print_mode': 'odoo',
        })
        picking = self._create_delivery()
        action = picking.button_validate()
        reports = action['params']['reports']
        self.assertEqual([r['report_name'] for r in reports],
                         ['stock.report_deliveryslip', self.label_report.report_name])
        self.assertFalse(reports[1]['context']['stock_auto_print_label_browser'])

    def test_disabled_does_not_print(self):
        self.delivery_type.write({'auto_print_shipping_label': False, 'auto_print_delivery_slip': False})
        picking = self._create_delivery()
        self.assertIs(picking.button_validate(), True)

    def test_label_template_renders(self):
        picking = self._create_delivery()
        picking.button_validate()
        html = self.env['ir.actions.report']._render_qweb_html(self.label_report.report_name, picking.ids)[0]
        html = html.decode()
        self.assertIn(picking.name, html)
        self.assertIn('Label Customer', html)
        self.assertIn('+855 12 345 678', html)
        self.assertIn('Label Test Product', html)
        self.assertIn('/report/barcode/?barcode_type=Code128', html)
