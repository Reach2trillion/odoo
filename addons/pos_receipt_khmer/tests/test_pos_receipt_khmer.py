import base64

from odoo.exceptions import UserError, ValidationError
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

    def test_paper_width_settings(self):
        """80 mm by default; 58 mm and its raster width are set from the POS settings and loaded."""
        config = self.main_pos_config
        self.assertEqual(config.kh_paper_width, '80')
        self.assertEqual(config.kh_raster_dots, 384)
        self.env['res.config.settings'].create({
            'pos_config_id': config.id,
            'pos_kh_paper_width': '58',
            'pos_kh_raster_dots': 360,
        })
        self.assertEqual(config.kh_paper_width, '58')
        self.assertEqual(config.kh_raster_dots, 360)
        settings = self.env['res.config.settings'].create({'pos_config_id': config.id})
        self.assertEqual(settings.pos_kh_paper_width, '58')
        self.assertFalse(settings.kh_pos_has_receipt_logo)
        with file_open('pos_receipt_khmer/static/img/abj_logo_print.png', 'rb') as f:
            self.company.kh_receipt_logo = base64.b64encode(f.read())
        settings.invalidate_recordset(['kh_pos_has_receipt_logo'])
        self.assertTrue(settings.kh_pos_has_receipt_logo)
        # the setting is in the POS settings form
        arch = self.env['res.config.settings'].get_views([(False, 'form')])['views']['form']['arch']
        self.assertIn('pos_kh_paper_width', arch)
        self.assertIn('pos_kh_raster_dots', arch)

        data = self._load_data()
        loaded = data['pos.config']['data'][0]
        self.assertEqual(loaded['kh_paper_width'], '58')
        self.assertEqual(loaded['kh_raster_dots'], 360)

    def test_raster_dots_range(self):
        config = self.main_pos_config
        for dots in (360, 384):
            config.kh_raster_dots = dots
        for dots in (0, 359, 385, 512):
            with self.assertRaises(ValidationError):
                config.kh_raster_dots = dots

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


# Sales Descriptions of the ABJ products on the live shop (English product name -> description_sale)
# and the Khmer receipt name the fill helper takes from each of them
ABJ_DESCRIPTIONS = {
    'BB Cream': ('ក្រែម BB ស្តើងស្រាល បិទបាំងបែបធម្មជាតិ ស្បែកភ្លឺថ្លា', 'ក្រែម BB'),
    'Body Lotion': ('ឡេលាបខ្លួន ផ្តល់សំណើមស្បែក ក្លិនក្រអូបស្រស់ស្រាយ', 'ឡេលាបខ្លួន'),
    'Foam': ('ហ្វូមលាងមុខ ជម្រះខ្លាញ់ និងគ្រឿងសម្អាង ស្អាតស្រស់ថ្លា', 'ហ្វូមលាងមុខ'),
    'Hair Conditioner': ('ក្រែមប្រែងសក់ ទន់រលោង គ្មានរញ៉េរញ៉ៃ', 'ក្រែមប្រែងសក់'),
    'Hair Shampoo': ('សាប៊ូកក់សក់ ស្អាតស្រស់ស្រាយរាល់ថ្ងៃ', 'សាប៊ូកក់សក់'),
    'Mask': ('ម៉ាសបិទមុខប្រចាំសប្តាហ៍ ឱ្យស្បែកភ្លឺថ្លា', 'ម៉ាសបិទមុខប្រចាំសប្តាហ៍'),
    'NightCream': ('ក្រែមយប់ ភ្ញាក់ឡើងស្បែកទន់ភ្លឺថ្លា', 'ក្រែមយប់'),
    'Remove MakeUp': ('ទឹកលុបគ្រឿងសម្អាង ជូតម្តងចេញអស់ ងាយស្រួល', 'ទឹកលុបគ្រឿងសម្អាង'),
    'Serum': ('សេរ៉ូមមុខស្រាលសិប ជ្រាបលឿន ស្បែកស្រស់ថ្លា', 'សេរ៉ូមមុខស្រាលសិប'),
    'ShowerGel': ('ទឹកងូតទឹក ក្លិនក្រអូប ស្រស់ស្រាយពេញមួយថ្ងៃ', 'ទឹកងូតទឹក'),
    'SunScreen': ('ឡេការពារកម្តៅថ្ងៃ ការពារស្បែកភ្លឺថ្លា', 'ឡេការពារកម្តៅថ្ងៃ'),
    'Underarm Cream': ('ក្រែមក្លៀក ស្អាតរលោង ជឿជាក់ពេញទំហឹង', 'ក្រែមក្លៀក'),
}


@tagged('post_install', '-at_install')
class TestPosReceiptKhmerNames(TestPointOfSaleHttpCommon):
    """Khmer product names on the receipt: receipt name, km_KH fallback, fill helper, setting, tour."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template = cls.env['product.template']

    def _load_data(self):
        self.main_pos_config.open_ui()
        return self.main_pos_config.current_session_id.load_data([])

    def _km_name(self, products):
        products.invalidate_recordset(['kh_pos_name_km', 'kh_pos_name_en'])
        return products.mapped('kh_pos_name_km')

    def test_khmer_name_loaded_in_pos(self):
        """The POS loads kh_pos_name_km with the product (core's product fields are still loaded)."""
        self.desk_pad.product_tmpl_id.kh_receipt_name = '  បន្ទះតុ '
        self.desk_pad.default_code = 'DP-1'
        data = self._load_data()
        fields = data['product.product']['fields']
        self.assertIn('kh_pos_name_km', fields)
        self.assertIn('kh_pos_name_en', fields)
        for fname in ('display_name', 'lst_price', 'product_tmpl_id', 'description_sale'):
            self.assertIn(fname, fields)
        products = {p['id']: p for p in data['product.product']['data']}
        self.assertEqual(products[self.desk_pad.id]['kh_pos_name_km'], 'បន្ទះតុ', "stripped receipt name")
        self.assertEqual(products[self.desk_pad.id]['kh_pos_name_en'], 'Desk Pad', "no [internal reference]")
        self.assertFalse(products[self.letter_tray.id]['kh_pos_name_km'])
        self.assertFalse(products[self.letter_tray.id]['kh_pos_name_en'], "only with a Khmer name")
        self.assertNotIn('kh_receipt_name', fields, "the POS only needs the computed name")

    def test_khmer_cashier_english_name(self):
        """A km_KH cashier loads the product names in Khmer: the English line comes from
        kh_pos_name_en (en_US, with the variant values), the Khmer name is unchanged."""
        self.env['res.lang']._activate_lang('km_KH')
        # "Foam": receipt name and a different km_KH translation; "SunScreen": translation only
        self.desk_pad.product_tmpl_id.kh_receipt_name = 'បន្ទះតុ'
        self.desk_pad.product_tmpl_id.with_context(lang='km_KH').name = 'បន្ទះ'
        self.letter_tray.product_tmpl_id.with_context(lang='km_KH').name = 'ថាសសំបុត្រ'
        # a variant: its attribute value is translated too
        size = self.env['product.attribute'].create({'name': 'KH Size', 'create_variant': 'always'})
        small, large = self.env['product.attribute.value'].create([
            {'name': 'Small', 'attribute_id': size.id},
            {'name': 'Large', 'attribute_id': size.id},
        ])
        small.with_context(lang='km_KH').name = 'តូច'
        chair = self.template.create({
            'name': 'KH Chair', 'available_in_pos': True, 'kh_receipt_name': 'កៅអី',
            'attribute_line_ids': [(0, 0, {'attribute_id': size.id, 'value_ids': [(6, 0, (small | large).ids)]})],
        })
        chair.with_context(lang='km_KH').name = 'កៅអីតូច'
        chair_small = chair.product_variant_ids.filtered(
            lambda p: p.product_template_attribute_value_ids.product_attribute_value_id == small)
        self.env.flush_all()

        self.main_pos_config.open_ui()
        session = self.main_pos_config.current_session_id
        for lang in ('km_KH', 'en_US'):
            data = session.with_context(lang=lang).load_data([])
            products = {p['id']: p for p in data['product.product']['data']}
            pad, tray = products[self.desk_pad.id], products[self.letter_tray.id]
            self.assertEqual(pad['kh_pos_name_km'], 'បន្ទះតុ', lang)
            self.assertEqual(pad['kh_pos_name_en'], 'Desk Pad', lang)
            self.assertEqual(tray['kh_pos_name_km'], 'ថាសសំបុត្រ', lang)
            self.assertEqual(tray['kh_pos_name_en'], 'Letter Tray', lang)
            if lang == 'km_KH':
                # what the receipt used to print as the "English" line
                self.assertEqual((pad['display_name'], tray['display_name']), ('បន្ទះ', 'ថាសសំបុត្រ'))
        # variants are not all loaded by load_data (limited loading): read them as the POS does
        variant = chair_small.with_context(lang='km_KH', display_default_code=False).read(
            ['display_name', 'kh_pos_name_km', 'kh_pos_name_en'])[0]
        self.assertEqual(variant['display_name'], 'កៅអីតូច (តូច)')
        self.assertEqual(variant['kh_pos_name_km'], 'កៅអី')
        self.assertEqual(variant['kh_pos_name_en'], 'KH Chair (Small)')

    def test_khmer_name_translation_fallback(self):
        """Without a receipt name: the km_KH translation of the name, if it is real Khmer."""
        products = self.desk_pad | self.letter_tray | self.whiteboard_pen
        self.assertEqual(self._km_name(products), ['', '', ''], "km_KH not active: no fallback")

        self.env['res.lang']._activate_lang('km_KH')
        self.desk_pad.product_tmpl_id.with_context(lang='km_KH').name = 'បន្ទះតុ'
        self.letter_tray.product_tmpl_id.with_context(lang='km_KH').name = 'Letter tray KH'  # no Khmer
        # whiteboard_pen: no km_KH translation (reads the en_US name)
        self.assertEqual(self.desk_pad.with_context(lang='en_US').name, 'Desk Pad')
        self.assertEqual(self._km_name(products), ['បន្ទះតុ', '', ''])

        # the receipt name wins over the translation
        self.desk_pad.product_tmpl_id.kh_receipt_name = 'កម្រាលតុ'
        self.assertEqual(self._km_name(products), ['កម្រាលតុ', '', ''])
        # a translation equal to the en_US name is not a Khmer name, even in Khmer script
        self.whiteboard_pen.product_tmpl_id.with_context(lang='en_US').name = 'ប៊ិច'
        self.whiteboard_pen.product_tmpl_id.with_context(lang='km_KH').name = 'ប៊ិច'
        self.assertEqual(self._km_name(products), ['កម្រាលតុ', '', ''])

        # batch: the same number of queries for 3 and for 40 products (no query per record)
        many = self.env['product.product'].create([{'name': f'KH batch {i}'} for i in range(40)])
        for product in many[:20]:
            product.product_tmpl_id.with_context(lang='km_KH').name = 'ផលិតផល'
        self.env.flush_all()

        def count(records):
            self.env.invalidate_all()
            before = self.env.cr.sql_log_count
            records.mapped('kh_pos_name_km')
            return self.env.cr.sql_log_count - before
        few, lot = count(products), count(many)
        self.assertLessEqual(lot, few, f"{lot} queries for 40 products, {few} for 3")
        self.assertEqual(self._km_name(many).count('ផលិតផល'), 20)

    def test_fill_name_from_description(self):
        """The first Khmer word of the Sales Description, plus the Latin words right after it."""
        model = self.template
        for key, (description, expected) in ABJ_DESCRIPTIONS.items():
            self.assertEqual(model._kh_name_from_description(description), expected, key)
        for description, expected in [
            ('ក្រែម SPF50+ 100ml ការពារ', 'ក្រែម SPF50+ 100ml'),
            ('ក្រែម ៥០ml ការពារ', 'ក្រែម ៥០ml'),            # Khmer digits
            ('ឡេ ១០០ ១២ដើម', 'ឡេ ១០០'),
            ('ក្រែម\u200b BB', 'ក្រែម BB'),
            ('  \n ឡេ\tការពារ', 'ឡេ'),
            # punctuation at the end of a word ends the name and is dropped
            ('ក្រែម, BB ស្តើង', 'ក្រែម'),
            ('ក្រែម BB, ស្តើង', 'ក្រែម BB'),
            ('ក្រែម BB. ថ្មី', 'ក្រែម BB'),
            ('ក្រែម។ ស្អាត', 'ក្រែម'),
            ('ក្រែម៖ BB', 'ក្រែម'),
            ('ផ្កាៗ ស', 'ផ្កាៗ'),               # the repetition sign is part of its word
            ('។ ក្រែម', ''),
            ('ក្រែម\u00a0BB\u00a0ស្តើង', 'ក្រែម BB'),   # no-break spaces (pasted text) separate words
            ('BB Cream ក្រែម', ''),            # does not start with a Khmer word
            ('ABJ ក្រែម BB', ''),
            ('', ''),
            (False, ''),
        ]:
            self.assertEqual(model._kh_name_from_description(description), expected, repr(description))

    def test_fill_action(self):
        """The Action-menu helper fills empty names only and reports what it skipped."""
        templates = self.template.create([
            {'name': f'ABJ-{key}', 'description_sale': description}
            for key, (description, _expected) in ABJ_DESCRIPTIONS.items()
        ])
        kept = self.template.create({
            'name': 'ABJ-Kept', 'description_sale': 'ក្រែមថ្មី ស្អាត', 'kh_receipt_name': 'ឈ្មោះចាស់',
        })
        latin = self.template.create({'name': 'ABJ-Latin', 'description_sale': 'Gentle foam ក្រែម'})
        empty = self.template.create({'name': 'ABJ-Empty'})

        action = self.env.ref('pos_receipt_khmer.action_kh_fill_receipt_name')
        self.assertEqual(action.binding_model_id.model, 'product.template')
        self.assertEqual(action.binding_view_types, 'list,form')
        everything = templates | kept | latin | empty
        result = action.with_context(active_model='product.template', active_ids=everything.ids).run()

        for template, (key, (_description, expected)) in zip(templates, ABJ_DESCRIPTIONS.items()):
            self.assertEqual(template.kh_receipt_name, expected, key)
        self.assertEqual(kept.kh_receipt_name, 'ឈ្មោះចាស់', "never overwrites a name")
        self.assertFalse(latin.kh_receipt_name)
        self.assertFalse(empty.kh_receipt_name)

        self.assertEqual(result['tag'], 'display_notification')
        message = result['params']['message']
        self.assertIn(f'{len(templates)} product(s) filled', message)
        self.assertIn('Skipped 3', message)
        for name in ('ABJ-Kept', 'ABJ-Latin', 'ABJ-Empty'):
            self.assertIn(name, message)
        # grouped by reason
        self.assertIn('already has a Khmer name (1): ABJ-Kept', message)
        self.assertIn('no Sales Description (1): ABJ-Empty', message)
        self.assertIn('does not start with a Khmer word (1): ABJ-Latin', message)
        self.assertTrue(result['params']['sticky'])
        self.assertEqual(result['params']['next']['tag'], 'soft_reload')

        # second run: nothing left to fill
        again = (templates | kept).action_kh_fill_receipt_name()
        self.assertIn('0 product(s) filled', again['params']['message'])
        self.assertNotIn('next', again['params'])

    def test_fill_translated_description(self):
        """The Sales Description is translatable: its km_KH value wins whatever the user's language."""
        self.env['res.lang']._activate_lang('km_KH')
        serum = self.template.with_context(lang='en_US').create({
            'name': 'ABJ-Serum EN', 'description_sale': 'Light serum, fast absorbing',
        })
        serum.with_context(lang='km_KH').description_sale = 'សេរ៉ូមមុខស្រាលសិប ជ្រាបលឿន'
        # Khmer kept in en_US and an English km_KH value: the user's language is tried too
        foam = self.template.with_context(lang='en_US').create({
            'name': 'ABJ-Foam EN', 'description_sale': 'ហ្វូមលាងមុខ ជម្រះខ្លាញ់',
        })
        foam.with_context(lang='km_KH').description_sale = 'Face foam'
        plain = self.template.with_context(lang='en_US').create({
            'name': 'ABJ-Plain', 'description_sale': 'Plain English text',
        })
        templates = (serum | foam | plain).with_context(lang='en_US')
        filled, skipped = templates._kh_fill_receipt_name()
        self.assertEqual(serum.kh_receipt_name, 'សេរ៉ូមមុខស្រាលសិប')
        self.assertEqual(foam.kh_receipt_name, 'ហ្វូមលាងមុខ')
        self.assertEqual(filled, serum | foam)
        self.assertEqual([t for t, _reason in skipped], [plain])

    def test_fill_action_access(self):
        """Only users who may write products see the fill action (others would get an access error)."""
        action = self.env.ref('pos_receipt_khmer.action_kh_fill_receipt_name')
        self.assertIn(self.env.ref('point_of_sale.group_pos_manager'), action.groups_id)

        def bound(user):
            bindings = self.env['ir.actions.actions'].with_user(user).get_bindings('product.template')
            return action.id in [a['id'] for a in bindings.get('action', [])]
        self.assertFalse(bound(self.pos_user), "a cashier cannot write products")
        self.assertTrue(bound(self.pos_admin))
        template = self.template.create({'name': 'ABJ-SunScreen', 'description_sale': ABJ_DESCRIPTIONS['SunScreen'][0]})
        action.with_user(self.pos_admin).with_context(
            active_model='product.template', active_ids=template.ids).run()
        self.assertEqual(template.kh_receipt_name, 'ឡេការពារកម្តៅថ្ងៃ')

    def test_product_names_setting_and_views(self):
        config = self.main_pos_config
        self.assertEqual(config.kh_product_names, 'both')
        self.env['res.config.settings'].create({'pos_config_id': config.id, 'pos_kh_product_names': 'km'})
        self.assertEqual(config.kh_product_names, 'km')
        arch = self.env['res.config.settings'].get_views([(False, 'form')])['views']['form']['arch']
        self.assertIn('pos_kh_product_names', arch)
        self.assertEqual(self._load_data()['pos.config']['data'][0]['kh_product_names'], 'km')

        views = self.template.get_views([(False, 'form'), (False, 'list')])['views']
        self.assertIn('o_kh_receipt_name', views['form']['arch'], "under the product name")
        self.assertIn('kh_receipt_name', views['form']['arch'])
        self.assertIn('kh_receipt_name', views['list']['arch'])
        variant_form = self.env['product.product'].get_views([(False, 'form')])['views']['form']['arch']
        self.assertIn('kh_receipt_name', variant_form)

    def test_khmer_names_tour(self):
        """Receipt: Khmer name + product name in "both", Khmer only in "km", English only in "en"."""
        self.desk_pad.product_tmpl_id.kh_receipt_name = 'បន្ទះតុ'
        self.letter_tray.product_tmpl_id.kh_receipt_name = 'ថាសដាក់សំបុត្រ ប្រើក្នុងការិយាល័យ សម្រាប់ឯកសារ និងសំបុត្រ'
        # words longer than a 58 mm line (360 dots)
        self.magnetic_board.product_tmpl_id.kh_receipt_name = 'អេប៊ីជេវ៉ាយធីននីងណៃរីផែរគ្រីមវិទនីយ៉ាស៊ីណាមីតអាំងវ៉េស្ទីស'
        self.monitor_stand.product_tmpl_id.kh_receipt_name = 'ជើងទ្រអេក្រង់ SuperUltraWideMonitorStandXL2000Pro'
        # a short word before a word that wraps inside itself onto 3+ lines at 360 dots (printed image)
        self.small_shelf.product_tmpl_id.name = 'ABJ Hyaluronic-Acid-Niacinamide-Ceramide-Serum'
        self.wall_shelf.product_tmpl_id.kh_receipt_name = 'ក្រែម ABJ-SuperUltraWideNightRepairCream-50ml'
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('pos_receipt_khmer_names_tour', login='pos_user')
