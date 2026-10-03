import base64

from odoo.exceptions import UserError
from odoo.tools.misc import file_open
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon

KH_COMPANY_FIELDS = ['kh_name', 'kh_address_km', 'kh_address_en', 'kh_doc_title', 'kh_tin_label', 'kh_has_receipt_logo']


@tagged('post_install', '-at_install')
class TestPosReceiptKhmer(TestPointOfSaleHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.main_pos_config.company_id
        cls.khr = cls.env.ref('base.KHR')
        cls.khr.active = True
        cls.env['res.currency.rate'].search([('currency_id', '=', cls.khr.id)]).unlink()
        cls.env['res.currency.rate'].create({
            'currency_id': cls.khr.id, 'company_id': cls.company.id, 'rate': 4100.0, 'name': '2020-01-01',
        })
        vals = {
            'kh_name': 'អេប៊ីជេ ស្គីនឃែរ',
            'kh_address_km': 'ក្រុងតាខ្មៅ ខេត្តកណ្ដាល',
            'kh_address_en': 'Ta Khmau, Kandal',
            'phone': '0312663333',
            'vat': '121200209',
        }
        if 'l10n_kh_exchange_rate' in cls.company._fields:
            vals['l10n_kh_exchange_rate'] = 4100.0
        cls.company.write(vals)
        pms = cls.main_pos_config.payment_method_ids
        cls.label_pm = pms.filtered(lambda pm: pm.type == 'bank')[:1] or pms.filtered(lambda pm: pm.type != 'cash')[:1]
        cls.label_pm.kh_receipt_label = 'ABA KHQR'

    def _load_data(self):
        self.main_pos_config.open_ui()
        return self.main_pos_config.current_session_id.load_data([])

    def test_pos_data_loaders(self):
        """The POS loads the receipt settings, the KHR currency and the payment-method label."""
        data = self._load_data()

        company_fields = data['res.company']['fields']
        for fname in KH_COMPANY_FIELDS:
            self.assertIn(fname, company_fields)
        self.assertNotIn('kh_receipt_logo', company_fields, "the binary logo must not be loaded into the POS")
        if 'l10n_kh_exchange_rate' in self.env['res.company']._fields:
            self.assertIn('l10n_kh_exchange_rate', company_fields)
        else:
            self.assertNotIn('l10n_kh_exchange_rate', company_fields)

        company = data['res.company']['data'][0]
        self.assertEqual(company['kh_name'], 'អេប៊ីជេ ស្គីនឃែរ')
        self.assertEqual(company['kh_address_en'], 'Ta Khmau, Kandal')
        self.assertEqual(company['kh_doc_title'], 'invoice')
        self.assertEqual(company['kh_tin_label'], 'tin')
        self.assertFalse(company['kh_has_receipt_logo'])
        # core fields are still there (the override extends, never replaces)
        for fname in ('name', 'vat', 'phone', 'city', 'state_id', 'currency_id'):
            self.assertIn(fname, company_fields)

        currencies = {c['name']: c for c in data['res.currency']['data']}
        self.assertIn('KHR', currencies, "KHR must be loaded into the POS")
        self.assertAlmostEqual(currencies['KHR']['rate'], 4100.0, places=2)
        self.assertIn(self.main_pos_config.currency_id.name, currencies, "the POS currency is still loaded")

        self.assertIn('kh_receipt_label', data['pos.payment.method']['fields'])
        labels = {pm['id']: pm['kh_receipt_label'] for pm in data['pos.payment.method']['data']}
        if self.label_pm:
            self.assertEqual(labels.get(self.label_pm.id), 'ABA KHQR')

    def test_inactive_khr_is_not_loaded(self):
        self.khr.active = False
        data = self._load_data()
        self.assertNotIn('KHR', [c['name'] for c in data['res.currency']['data']])
        self.assertIn(self.main_pos_config.currency_id.name, [c['name'] for c in data['res.currency']['data']])

    def test_receipt_logo_flag(self):
        with file_open('pos_receipt_khmer/static/img/abj_logo_print.png', 'rb') as f:
            self.company.kh_receipt_logo = base64.b64encode(f.read())
        self.assertTrue(self.company.kh_has_receipt_logo)
        self.company.kh_receipt_logo = False
        self.assertFalse(self.company.kh_has_receipt_logo)

    def test_receipt_label_editable_with_open_session(self):
        """The receipt label is cosmetic: it can change while a session is open (core fields cannot)."""
        self.main_pos_config.open_ui()
        pm = self.main_pos_config.payment_method_ids[:1]
        self.assertTrue(pm.open_session_ids)
        pm.kh_receipt_label = 'Receipt label'
        self.assertEqual(pm.kh_receipt_label, 'Receipt label')
        with self.assertRaises(UserError):
            pm.write({'name': 'Renamed', 'kh_receipt_label': 'Other'})

    def test_receipt_tour(self):
        """Pay an order in the POS and check the bilingual receipt (.o_kh_receipt, TOTAL, KHR, change)."""
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('pos_receipt_khmer_tour', login='pos_user')
