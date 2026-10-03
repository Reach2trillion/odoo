from odoo.tests import tagged
from odoo.tests.common import BaseCase

from odoo.addons.pos_aba_khqr.tools import khqr

NOW = 1790000000000
EXP = NOW + 5 * 60 * 1000

# Generated with the official NBC SDK (npm bakong-khqr 1.0.20, Date.now = NOW).
SDK = {
    'ind_usd': '00020101021229190015abjskincare@aba52045999530384054046.505802KH5912ABJ SkinCare'
               '6010Phnom Penh62380120Order 00002-001-00030710BOOTH SHOP9934001317900000000000113'
               '1790000300000630413F6',
    'ind_khr': '00020101021229440015abjskincare@aba01090123456780208ABA Bank52045999530311654052400'
               '05802KH5912ABJ SkinCare6009Siem Reap993400131790000000000011317900003000006304'
               '42E3',
    'ind_usd_int': '00020101021229190015abjskincare@aba520459995303840540165802KH5912ABJ SkinCare'
                   '6010Phnom Penh993400131790000000000011317900003000006304B4F2',
    'mer_usd': '00020101021230440015abjskincare@aba01090001234560208ABA Bank5204599953038405405'
               '12.345802KH5912ABJ SkinCare6010Phnom Penh62180105INV-10305Booth99340013179000000'
               '000001131790000300000630401FB',
    'mer_static': '00020101021130440015abjskincare@aba01090001234560208ABA Bank52045999530384058'
                  '02KH5912ABJ SkinCare6010Phnom Penh62090305Booth63044CB7',
}


@tagged('post_install', '-at_install', 'pos_aba_khqr')
class TestKhqr(BaseCase):

    def test_matches_official_sdk(self):
        self.assertEqual(SDK['ind_usd'], khqr.build_individual(
            'abjskincare@aba', 'ABJ SkinCare', 'USD', 6.5, 'Phnom Penh',
            expires_ms=EXP, now_ms=NOW,
            bill_number='Order 00002-001-0003', terminal_label='BOOTH SHOP'))
        self.assertEqual(SDK['ind_khr'], khqr.build_individual(
            'abjskincare@aba', 'ABJ SkinCare', 'KHR', 24000, 'Siem Reap',
            account_information='012345678', acquiring_bank='ABA Bank',
            expires_ms=EXP, now_ms=NOW))
        self.assertEqual(SDK['ind_usd_int'], khqr.build_individual(
            'abjskincare@aba', 'ABJ SkinCare', 'USD', 6.0, 'Phnom Penh',
            expires_ms=EXP, now_ms=NOW))
        self.assertEqual(SDK['mer_usd'], khqr.build_merchant(
            'abjskincare@aba', '000123456', 'ABA Bank', 'ABJ SkinCare', 'USD', 12.34,
            'Phnom Penh', expires_ms=EXP, now_ms=NOW, bill_number='INV-1', store_label='Booth'))
        self.assertEqual(SDK['mer_static'], khqr.build_merchant(
            'abjskincare@aba', '000123456', 'ABA Bank', 'ABJ SkinCare', 'USD', None,
            'Phnom Penh', store_label='Booth'))

    def test_static_sticker_to_dynamic(self):
        dynamic = khqr.from_static(SDK['mer_static'], 'USD', 12.34, EXP, now_ms=NOW,
                                   bill_number='INV-1')
        self.assertEqual(dynamic, SDK['mer_usd'])
        data = khqr.decode(dynamic)
        self.assertEqual(data['01'], khqr.DYNAMIC_QR)
        self.assertEqual(data['30'], {'00': 'abjskincare@aba', '01': '000123456', '02': 'ABA Bank'})
        self.assertEqual(data['99'], {'00': str(NOW), '01': str(EXP)})

    def test_from_source_accepts_bakong_id(self):
        qr = khqr.from_source('abjskincare@aba', 'USD', 6.5, EXP, merchant_name='ABJ SkinCare',
                              merchant_city='Phnom Penh', now_ms=NOW,
                              bill_number='Order 00002-001-0003', terminal_label='BOOTH SHOP')
        self.assertEqual(qr, SDK['ind_usd'])

    def test_khr_must_be_whole_riel(self):
        with self.assertRaises(khqr.KHQRError):
            khqr.format_amount(4000.5, 'KHR')
        self.assertEqual(khqr.format_amount(4000, 'KHR'), '4000')
        self.assertEqual(khqr.format_amount(6.005, 'USD'), '6.01')
        self.assertEqual(khqr.format_amount(6.1, 'USD'), '6.10')

    def test_rejects_bad_input(self):
        tampered = SDK['mer_static'][:-1] + ('0' if SDK['mer_static'][-1] != '0' else '1')
        with self.assertRaises(khqr.KHQRError):
            khqr.from_static(tampered, 'USD', 1, EXP, now_ms=NOW)
        with self.assertRaises(khqr.KHQRError):
            khqr.build_individual('no-at-sign', 'Shop', 'USD', 1, expires_ms=EXP, now_ms=NOW)
        with self.assertRaises(khqr.KHQRError):
            khqr.build_individual('shop@aba', 'Shop', 'EUR', 1, expires_ms=EXP, now_ms=NOW)
        with self.assertRaises(khqr.KHQRError):
            khqr.build_individual('shop@aba', 'Shop', 'USD', 1, expires_ms=None, now_ms=NOW)

    def test_non_latin_labels_are_dropped(self):
        qr = khqr.build_individual('abjskincare@aba', 'ABJ SkinCare', 'USD', 6, 'Phnom Penh',
                                   expires_ms=EXP, now_ms=NOW, terminal_label='ហាង Booth')
        self.assertEqual(khqr.decode(qr)['62'], {'07': 'Booth'})
