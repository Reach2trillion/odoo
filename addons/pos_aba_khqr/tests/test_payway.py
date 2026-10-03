import base64
import hashlib
import hmac
from unittest.mock import MagicMock, patch

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from odoo.addons.pos_aba_khqr.tools import payway

API_KEY = 'test-api-key'
MERCHANT = 'abjskincare'


def _expected_hash(*values):
    message = ''.join(values).encode()
    return base64.b64encode(hmac.new(API_KEY.encode(), message, hashlib.sha512).digest()).decode()


def _response(data):
    response = MagicMock()
    response.json.return_value = data
    response.status_code = 200
    return response


@tagged('post_install', '-at_install', 'pos_aba_khqr')
class TestPayWay(BaseCase):

    def setUp(self):
        super().setUp()
        self.client = payway.PayWayClient(MERCHANT, API_KEY, 'sandbox')

    @patch.object(payway, 'request_time', return_value='20261003120000')
    def test_generate_qr_signature(self, _mock_time):
        with patch.object(payway.requests, 'post', return_value=_response({
            'status': {'code': '0', 'message': 'Success'},
            'qrString': '000201010212',
            'abapay_deeplink': 'abamobilebank://x',
        })) as post:
            result = self.client.generate_qr(
                'K261003120000ABCDEF', '6.00', 'USD', 5, 'template3_color',
                callback_url='https://abjskincare.com/pos/aba_khqr/webhook')
        self.assertEqual(result['qrString'], '000201010212')
        url = post.call_args.args[0]
        body = post.call_args.kwargs['json']
        self.assertEqual(url, 'https://checkout-sandbox.payway.com.kh'
                              '/api/payment-gateway/v1/payments/generate-qr')
        callback = base64.b64encode(b'https://abjskincare.com/pos/aba_khqr/webhook').decode()
        self.assertEqual(body['callback_url'], callback)
        # req_time, merchant_id, tran_id, amount, items, first_name, last_name, email,
        # phone, purchase_type, payment_option, callback_url, return_deeplink, currency,
        # custom_fields, return_params, payout, lifetime, qr_image_template
        self.assertEqual(body['hash'], _expected_hash(
            '20261003120000', MERCHANT, 'K261003120000ABCDEF', '6.00', '', '', '', '', '',
            'purchase', 'abapay_khqr', callback, '', 'USD', '', '', '', '5', 'template3_color'))
        self.assertNotIn('items', body)

    @patch.object(payway, 'request_time', return_value='20261003120000')
    def test_check_transaction_signature(self, _mock_time):
        with patch.object(payway.requests, 'post', return_value=_response({
            'data': {'payment_status_code': 0, 'payment_status': 'APPROVED'},
            'status': {'code': '00'},
        })) as post:
            result = self.client.check_transaction('K1')
        self.assertTrue(payway.is_success(result))
        body = post.call_args.kwargs['json']
        self.assertTrue(post.call_args.args[0].endswith('/payments/check-transaction-2'))
        self.assertEqual(body['hash'], _expected_hash('20261003120000', MERCHANT, 'K1'))

    @patch.object(payway, 'request_time', return_value='20261003120000')
    def test_purchase_khqr_signature(self, _mock_time):
        with patch.object(payway.requests, 'post', return_value=_response({
            'status': {'code': '00', 'message': 'Success!'},
            'qr_string': '000201010212',
            'abapay_deeplink': 'abamobilebank://x',
        })) as post:
            result = self.client.purchase_khqr('K1', '6.00', 'USD', 5,
                                               callback_url='https://a.b/hook')
        self.assertEqual(result['qrString'], '000201010212')
        self.assertTrue(post.call_args.args[0].endswith('/payments/purchase'))
        form = {key: value[1] for key, value in post.call_args.kwargs['files'].items()}
        callback = base64.b64encode(b'https://a.b/hook').decode()
        self.assertEqual(form['payment_option'], 'abapay_khqr_deeplink')
        self.assertEqual(form['return_url'], callback)
        # req_time, merchant_id, tran_id, amount, items, shipping, firstname, lastname,
        # email, phone, type, payment_option, return_url, cancel_url,
        # continue_success_url, return_deeplink, currency, custom_fields,
        # return_params, payout, lifetime, additional_params, google_pay_token,
        # skip_success_page
        self.assertEqual(form['hash'], _expected_hash(
            '20261003120000', MERCHANT, 'K1', '6.00', '', '', '', '', '', '', 'purchase',
            'abapay_khqr_deeplink', callback, '', '', '', 'USD', '', '', '', '5', '', '', ''))

    def test_refused_request_raises(self):
        with patch.object(payway.requests, 'post', return_value=_response({
            'status': {'code': '5', 'message': 'Wrong hash'},
        })):
            with self.assertRaises(payway.PayWayError):
                self.client.generate_qr('K1', '1.00', 'USD', 5, 'template3_color')

    def test_lifetime_limits(self):
        with self.assertRaises(payway.PayWayError):
            self.client.generate_qr('K1', '1.00', 'USD', 2, 'template3_color')
