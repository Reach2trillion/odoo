"""Minimal ABA PayWay client for the QR API (dynamic ABA KHQR).

Pure Python (only ``requests``) so the signing logic can be unit tested.
Docs: https://developer.payway.com.kh/qr-api-14530840e0
"""
import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import requests

_logger = logging.getLogger(__name__)

BASE_URLS = {
    'production': 'https://checkout.payway.com.kh',
    'sandbox': 'https://checkout-sandbox.payway.com.kh',
}
GENERATE_QR_PATH = '/api/payment-gateway/v1/payments/generate-qr'
CHECK_TRANSACTION_PATH = '/api/payment-gateway/v1/payments/check-transaction-2'
CLOSE_TRANSACTION_PATH = '/api/payment-gateway/v1/payments/close-transaction'
PURCHASE_PATH = '/api/payment-gateway/v1/payments/purchase'

# Order of the values concatenated before signing a purchase request.
PURCHASE_HASH_FIELDS = (
    'req_time', 'merchant_id', 'tran_id', 'amount', 'items', 'shipping',
    'firstname', 'lastname', 'email', 'phone', 'type', 'payment_option',
    'return_url', 'cancel_url', 'continue_success_url', 'return_deeplink',
    'currency', 'custom_fields', 'return_params', 'payout', 'lifetime',
    'additional_params', 'google_pay_token', 'skip_success_page',
)

# Order of the values concatenated before signing a generate-qr request.
QR_HASH_FIELDS = (
    'req_time', 'merchant_id', 'tran_id', 'amount', 'items', 'first_name',
    'last_name', 'email', 'phone', 'purchase_type', 'payment_option',
    'callback_url', 'return_deeplink', 'currency', 'custom_fields',
    'return_params', 'payout', 'lifetime', 'qr_image_template',
)

# payment_status_code returned by check-transaction-2
STATUS_APPROVED = 0
STATUS_PENDING = 2
STATUS_DECLINED = 3
STATUS_REFUNDED = 4
STATUS_CANCELLED = 7

MIN_LIFETIME = 3          # minutes, PayWay minimum
MAX_LIFETIME = 43200      # minutes (30 days), PayWay maximum


class PayWayError(Exception):
    def __init__(self, message, code=None, response=None):
        super().__init__(message)
        self.code = code
        self.response = response


def request_time():
    return datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')


def sign(api_key, *values):
    """Base64(HMAC-SHA512(concat(values), api_key)); ``None`` counts as ''."""
    message = ''.join('' if value is None else str(value) for value in values)
    digest = hmac.new(api_key.encode(), message.encode(), hashlib.sha512).digest()
    return base64.b64encode(digest).decode()


def b64(text):
    return base64.b64encode(text.encode()).decode() if text else ''


def is_success(payload):
    code = str(((payload or {}).get('status') or {}).get('code', ''))
    return code in ('0', '00')


class PayWayClient:
    def __init__(self, merchant_id, api_key, environment='production', timeout=20):
        if environment not in BASE_URLS:
            raise PayWayError('Unknown PayWay environment %r.' % environment)
        if not merchant_id or not api_key:
            raise PayWayError('The PayWay merchant ID and API key are required.')
        self.merchant_id = merchant_id.strip()
        self.api_key = api_key.strip()
        self.environment = environment
        self.timeout = timeout

    def _post(self, path, payload):
        url = BASE_URLS[self.environment] + path
        try:
            response = requests.post(url, json=payload, timeout=self.timeout,
                                     headers={'Accept': 'application/json'})
        except requests.RequestException as error:
            raise PayWayError('Cannot reach ABA PayWay: %s' % error) from error
        try:
            data = response.json()
        except ValueError:
            raise PayWayError('ABA PayWay answered HTTP %s with an unreadable body.'
                              % response.status_code, code=response.status_code)
        _logger.debug('PayWay %s -> %s', path, json.dumps(data)[:2000])
        return data

    def generate_qr(self, tran_id, amount, currency, lifetime, qr_image_template,
                    callback_url=None, payment_option='abapay_khqr',
                    purchase_type='purchase', **optional):
        """Create a dynamic KHQR. ``amount`` must already be a formatted string."""
        lifetime = int(lifetime or MIN_LIFETIME)
        if not MIN_LIFETIME <= lifetime <= MAX_LIFETIME:
            raise PayWayError('The QR lifetime must be between %d and %d minutes.'
                              % (MIN_LIFETIME, MAX_LIFETIME))
        values = {
            'req_time': request_time(),
            'merchant_id': self.merchant_id,
            'tran_id': tran_id,
            'amount': amount,
            'purchase_type': purchase_type,
            'payment_option': payment_option,
            'callback_url': b64(callback_url),
            'currency': currency,
            'lifetime': lifetime,
            'qr_image_template': qr_image_template,
        }
        values.update({key: value for key, value in optional.items() if value})
        values['hash'] = sign(self.api_key, *(values.get(field) for field in QR_HASH_FIELDS))
        payload = {key: value for key, value in values.items() if value not in (None, '')}
        data = self._post(GENERATE_QR_PATH, payload)
        if not is_success(data) or not data.get('qrString'):
            status = data.get('status') or {}
            raise PayWayError('ABA PayWay refused the QR request: %s'
                              % (status.get('message') or data),
                              code=status.get('code'), response=data)
        return data

    def purchase_khqr(self, tran_id, amount, currency, lifetime, callback_url=None):
        """KHQR through the Purchase API (``abapay_khqr_deeplink``).

        Works on merchant accounts where ABA has not enabled the QR API: the
        Purchase API is the one the eCommerce checkout uses. Returns the same
        keys as :meth:`generate_qr` (``qrString``, ``abapay_deeplink``).
        """
        lifetime = int(lifetime or MIN_LIFETIME)
        values = {
            'req_time': request_time(),
            'merchant_id': self.merchant_id,
            'tran_id': tran_id,
            'amount': amount,
            'type': 'purchase',
            'payment_option': 'abapay_khqr_deeplink',
            'return_url': b64(callback_url),
            'currency': currency,
            'lifetime': lifetime,
        }
        values['hash'] = sign(self.api_key, *(values.get(field) for field in PURCHASE_HASH_FIELDS))
        form = {key: (None, str(value)) for key, value in values.items() if value not in (None, '')}
        url = BASE_URLS[self.environment] + PURCHASE_PATH
        try:
            response = requests.post(url, files=form, timeout=self.timeout,
                                     headers={'Accept': 'application/json'})
        except requests.RequestException as error:
            raise PayWayError('Cannot reach ABA PayWay: %s' % error) from error
        try:
            data = response.json()
        except ValueError:
            raise PayWayError('ABA PayWay answered HTTP %s without JSON (is the KHQR '
                              'deeplink option enabled?).' % response.status_code,
                              code=response.status_code)
        qr_string = data.get('qr_string') or data.get('qrString')
        if not is_success(data) or not qr_string:
            status = data.get('status') or {}
            raise PayWayError('ABA PayWay refused the KHQR purchase: %s'
                              % (status.get('message') or data),
                              code=status.get('code'), response=data)
        data['qrString'] = qr_string
        return data

    def check_transaction(self, tran_id):
        req_time = request_time()
        return self._post(CHECK_TRANSACTION_PATH, {
            'req_time': req_time,
            'merchant_id': self.merchant_id,
            'tran_id': tran_id,
            'hash': sign(self.api_key, req_time, self.merchant_id, tran_id),
        })

    def close_transaction(self, tran_id):
        req_time = request_time()
        return self._post(CLOSE_TRANSACTION_PATH, {
            'req_time': req_time,
            'merchant_id': self.merchant_id,
            'tran_id': tran_id,
            'hash': sign(self.api_key, req_time, self.merchant_id, tran_id),
        })
