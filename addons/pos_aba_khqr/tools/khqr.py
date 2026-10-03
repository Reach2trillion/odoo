"""KHQR encoder / decoder (Cambodia's EMVCo merchant-presented QR).

Pure Python on purpose (no Odoo import) so it can be unit tested on its own.
Output matches the official ``bakong-khqr`` SDK published by the National
Bank of Cambodia (tag order, length rules, CRC-16/CCITT-FALSE, tag 99
creation/expiration timestamps for dynamic QR).
"""
import hashlib
import re
import time
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CURRENCY_CODES = {'KHR': '116', 'USD': '840'}
CURRENCY_NAMES = {code: name for name, code in CURRENCY_CODES.items()}
DEFAULT_MCC = '5999'
DEFAULT_CITY = 'Phnom Penh'

STATIC_QR = '11'
DYNAMIC_QR = '12'

TAG_INDIVIDUAL = '29'
TAG_MERCHANT = '30'
TAG_ADDITIONAL_DATA = '62'
TAG_LANGUAGE_TEMPLATE = '64'
TAG_TIMESTAMP = '99'
TAG_CRC = '63'

# Sub tags of tag 62 (additional data)
SUB_BILL_NUMBER = '01'
SUB_MOBILE_NUMBER = '02'
SUB_STORE_LABEL = '03'
SUB_TERMINAL_LABEL = '07'
SUB_PURPOSE = '08'

# Length limits from the NBC SDK (``emv.INVALID_LENGTH``)
MAX_LEN = {
    'merchant_name': 25,
    'merchant_city': 15,
    'bakong_account': 32,
    'amount': 13,
    'bill_number': 25,
    'store_label': 25,
    'terminal_label': 25,
    'mobile_number': 25,
    'purpose': 25,
    'merchant_id': 32,
    'acquiring_bank': 32,
    'account_information': 32,
}

# Tags a static KHQR may carry that we keep when turning it into a dynamic one
_MERCHANT_ACCOUNT_TAGS = {'%02d' % tag for tag in range(2, 52)}


class KHQRError(ValueError):
    """Raised when a KHQR payload cannot be built or parsed."""


def crc16(data):
    """CRC-16/CCITT-FALSE as required by EMVCo (poly 0x1021, init 0xFFFF)."""
    crc = 0xFFFF
    for byte in data.encode('utf-8'):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return '%04X' % crc


def tlv(tag, value):
    value = str(value)
    if not value:
        raise KHQRError('Tag %s cannot be empty.' % tag)
    if len(value) > 99:
        raise KHQRError('Tag %s is too long (%d characters, max 99).' % (tag, len(value)))
    return '%s%02d%s' % (tag, len(value), value)


def parse_tlv(payload):
    """Split an EMV string into an ordered list of ``(tag, value)``."""
    items = []
    pos = 0
    while pos < len(payload):
        header = payload[pos:pos + 4]
        if len(header) < 4 or not header.isdigit():
            raise KHQRError('Invalid KHQR data near position %d.' % pos)
        tag, length = header[:2], int(header[2:])
        value = payload[pos + 4:pos + 4 + length]
        if len(value) != length:
            raise KHQRError('Truncated KHQR data in tag %s.' % tag)
        items.append((tag, value))
        pos += 4 + length
    return items


def check_crc(payload):
    if len(payload) < 8 or payload[-8:-4] != TAG_CRC + '04':
        return False
    return crc16(payload[:-4]) == payload[-4:].upper()


def decode(payload, verify_crc=True):
    """Return a dict ``{tag: value}``; nested templates become ``{sub_tag: value}``.

    Only the templates KHQR defines as nested (29, 30, 62, 64, 99) are split.
    """
    payload = (payload or '').strip()
    if verify_crc and not check_crc(payload):
        raise KHQRError('This is not a valid KHQR (checksum mismatch).')
    result = {}
    for tag, value in parse_tlv(payload):
        if tag in (TAG_INDIVIDUAL, TAG_MERCHANT, TAG_ADDITIONAL_DATA,
                   TAG_LANGUAGE_TEMPLATE, TAG_TIMESTAMP):
            try:
                value = dict(parse_tlv(value))
            except KHQRError:
                pass
        result[tag] = value
    return result


def md5(payload):
    """MD5 of the full KHQR string; the key Bakong uses to look a payment up."""
    return hashlib.md5(payload.encode('utf-8')).hexdigest()


def format_amount(amount, currency):
    """Format like the SDK: KHR must be whole riel, USD has at most 2 decimals."""
    try:
        value = Decimal(str(amount))
    except InvalidOperation:
        raise KHQRError('Invalid amount: %r' % (amount,))
    if value <= 0:
        raise KHQRError('The amount must be greater than zero.')
    if currency == 'KHR':
        if value != value.to_integral_value():
            raise KHQRError('KHR amounts must be whole riel (got %s).' % value)
        text = str(int(value))
    else:
        value = value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        text = str(int(value)) if value == value.to_integral_value() else '%.2f' % value
    if len(text) > MAX_LEN['amount']:
        raise KHQRError('The amount is too large for KHQR.')
    return text


def _check_len(name, value):
    if value and len(value) > MAX_LEN[name]:
        raise KHQRError('%s is too long (max %d characters).'
                        % (name.replace('_', ' ').capitalize(), MAX_LEN[name]))


def _check_text(name, value):
    """Merchant name / city / labels must be plain ASCII in tags 59-62."""
    if value and not re.fullmatch(r'[\x20-\x7E]+', value):
        raise KHQRError('%s must use Latin letters only (no Khmer script).'
                        % name.replace('_', ' ').capitalize())


def _currency_code(currency):
    code = CURRENCY_CODES.get((currency or '').upper())
    if not code:
        raise KHQRError('KHQR only supports USD and KHR, not %s.' % currency)
    return code


def _timestamp(expires_ms, now_ms=None):
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    expires_ms = int(expires_ms)
    if len(str(expires_ms)) != 13:
        raise KHQRError('The expiration must be a 13-digit millisecond timestamp.')
    if expires_ms <= now_ms:
        raise KHQRError('The expiration time is already in the past.')
    return tlv('00', now_ms) + tlv('01', expires_ms)


def _additional_data(existing=None, bill_number=None, mobile_number=None,
                     store_label=None, terminal_label=None, purpose=None):
    data = dict(existing or {})
    for sub, name, value in (
        (SUB_BILL_NUMBER, 'bill_number', bill_number),
        (SUB_MOBILE_NUMBER, 'mobile_number', mobile_number),
        (SUB_STORE_LABEL, 'store_label', store_label),
        (SUB_TERMINAL_LABEL, 'terminal_label', terminal_label),
        (SUB_PURPOSE, 'purpose', purpose),
    ):
        # Labels are informative only: drop non-Latin characters (e.g. a POS
        # named in Khmer) instead of refusing to build the QR.
        value = re.sub(r'[^\x20-\x7E]', '', str(value or '')).strip()[:MAX_LEN[name]].strip()
        if value:
            data[sub] = value
    return ''.join(tlv(sub, data[sub]) for sub in sorted(data) if data[sub])


def build(account_tag, account_value, merchant_name, currency, amount=None,
          merchant_city=DEFAULT_CITY, mcc=DEFAULT_MCC, additional_data='',
          language_template='', extra_tags=(), expires_ms=None, now_ms=None):
    """Assemble a KHQR string from already encoded parts.

    ``amount`` empty -> static QR (customer types the amount).
    ``amount`` set   -> dynamic QR, which KHQR requires to carry an expiration.
    """
    if account_tag not in _MERCHANT_ACCOUNT_TAGS:
        raise KHQRError('Invalid merchant account tag %s.' % account_tag)
    _check_len('merchant_name', merchant_name)
    _check_len('merchant_city', merchant_city)
    currency_code = _currency_code(currency)
    dynamic = amount not in (None, '', 0)

    parts = [tlv('00', '01'), tlv('01', DYNAMIC_QR if dynamic else STATIC_QR)]
    for tag, value in extra_tags:
        if tag == '15' and currency_code == CURRENCY_CODES['USD']:
            continue  # UnionPay data is only valid for KHR QR codes
        parts.append(tlv(tag, value))
    parts.append(tlv(account_tag, account_value))
    parts.append(tlv('52', mcc or DEFAULT_MCC))
    parts.append(tlv('53', currency_code))
    if dynamic:
        parts.append(tlv('54', format_amount(amount, CURRENCY_NAMES[currency_code])))
    parts.append(tlv('58', 'KH'))
    parts.append(tlv('59', merchant_name))
    parts.append(tlv('60', merchant_city or DEFAULT_CITY))
    if additional_data:
        parts.append(tlv(TAG_ADDITIONAL_DATA, additional_data))
    if language_template:
        parts.append(tlv(TAG_LANGUAGE_TEMPLATE, language_template))
    if dynamic:
        if not expires_ms:
            raise KHQRError('A KHQR with an amount must have an expiration time.')
        parts.append(tlv(TAG_TIMESTAMP, _timestamp(expires_ms, now_ms)))
    payload = ''.join(parts) + TAG_CRC + '04'
    return payload + crc16(payload)


def build_individual(bakong_account_id, merchant_name, currency, amount=None,
                     merchant_city=DEFAULT_CITY, account_information=None,
                     acquiring_bank=None, expires_ms=None, now_ms=None, **labels):
    """KHQR for an individual Bakong account (tag 29), e.g. ``name@aba``."""
    bakong_account_id = (bakong_account_id or '').strip()
    if '@' not in bakong_account_id:
        raise KHQRError('A Bakong account ID looks like "name@bank".')
    _check_len('bakong_account', bakong_account_id)
    _check_len('account_information', account_information)
    _check_len('acquiring_bank', acquiring_bank)
    _check_text('merchant_name', merchant_name)
    _check_text('merchant_city', merchant_city)
    account = tlv('00', bakong_account_id)
    if account_information:
        account += tlv('01', account_information)
    if acquiring_bank:
        account += tlv('02', acquiring_bank)
    return build(TAG_INDIVIDUAL, account, merchant_name, currency, amount=amount,
                 merchant_city=merchant_city, additional_data=_additional_data(**labels),
                 expires_ms=expires_ms, now_ms=now_ms)


def build_merchant(bakong_account_id, merchant_id, acquiring_bank, merchant_name,
                   currency, amount=None, merchant_city=DEFAULT_CITY,
                   expires_ms=None, now_ms=None, **labels):
    """KHQR for a merchant account (tag 30)."""
    bakong_account_id = (bakong_account_id or '').strip()
    if '@' not in bakong_account_id:
        raise KHQRError('A Bakong account ID looks like "name@bank".')
    if not merchant_id or not acquiring_bank:
        raise KHQRError('A merchant KHQR needs a merchant ID and an acquiring bank.')
    _check_len('bakong_account', bakong_account_id)
    _check_len('merchant_id', merchant_id)
    _check_len('acquiring_bank', acquiring_bank)
    _check_text('merchant_name', merchant_name)
    _check_text('merchant_city', merchant_city)
    account = tlv('00', bakong_account_id) + tlv('01', merchant_id) + tlv('02', acquiring_bank)
    return build(TAG_MERCHANT, account, merchant_name, currency, amount=amount,
                 merchant_city=merchant_city, additional_data=_additional_data(**labels),
                 expires_ms=expires_ms, now_ms=now_ms)


def from_static(static_qr, currency, amount, expires_ms, now_ms=None, **labels):
    """Turn the shop's static KHQR (e.g. the ABA sticker) into a dynamic KHQR.

    The bank-issued account data (tags 02-51), merchant name, city, MCC and
    language template are kept untouched; only the amount, currency, bill
    number / terminal label and the expiration are set.
    """
    items = parse_tlv((static_qr or '').strip())
    if not check_crc(static_qr.strip()):
        raise KHQRError('The KHQR text is incomplete or mistyped (checksum mismatch).')
    values = dict(items)
    account = [(tag, value) for tag, value in items if tag in _MERCHANT_ACCOUNT_TAGS]
    bakong = [(tag, value) for tag, value in account if tag in (TAG_INDIVIDUAL, TAG_MERCHANT)]
    if not bakong:
        raise KHQRError('This QR code has no Bakong account (tag 29/30), so it is not a KHQR.')
    account_tag, account_value = bakong[0]
    extra = [(tag, value) for tag, value in account if (tag, value) != bakong[0]]
    existing_62 = {}
    if values.get(TAG_ADDITIONAL_DATA):
        existing_62 = dict(parse_tlv(values[TAG_ADDITIONAL_DATA]))
    return build(
        account_tag, account_value,
        merchant_name=values.get('59') or '',
        currency=currency, amount=amount,
        merchant_city=values.get('60') or DEFAULT_CITY,
        mcc=values.get('52') or DEFAULT_MCC,
        additional_data=_additional_data(existing_62, **labels),
        language_template=values.get(TAG_LANGUAGE_TEMPLATE, ''),
        extra_tags=extra,
        expires_ms=expires_ms, now_ms=now_ms,
    )


def from_source(source, currency, amount, expires_ms, merchant_name=None,
                merchant_city=None, now_ms=None, **labels):
    """Build a dynamic KHQR from what the user configured.

    ``source`` is either the full text of an existing static KHQR (starts
    with ``000201``) or a bare Bakong account ID such as ``myshop@aba``.
    """
    source = (source or '').strip()
    if not source:
        raise KHQRError('Set your KHQR text or Bakong account ID first.')
    if source.startswith('000201'):
        return from_static(source, currency, amount, expires_ms, now_ms=now_ms, **labels)
    if not merchant_name:
        raise KHQRError('Set the merchant name shown to customers.')
    return build_individual(source, merchant_name, currency, amount=amount,
                            merchant_city=merchant_city or DEFAULT_CITY,
                            expires_ms=expires_ms, now_ms=now_ms, **labels)
