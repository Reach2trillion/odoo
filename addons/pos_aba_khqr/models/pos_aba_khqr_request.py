import base64
import io
import json
import logging
import re
import secrets
from datetime import timedelta, timezone

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

from ..tools import khqr
from ..tools.payway import (
    STATUS_APPROVED,
    STATUS_CANCELLED,
    STATUS_DECLINED,
    STATUS_REFUNDED,
    PayWayError,
    is_success,
)

_logger = logging.getLogger(__name__)

try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_Q
except ImportError:  # Odoo normally ships qrcode (auth_totp needs it)
    qrcode = None

# Seconds between two PayWay status calls for the same QR (POS polls every 3s).
CHECK_THROTTLE_SECONDS = 3
# A payment started just before expiry may need a few seconds to settle.
EXPIRY_GRACE_SECONDS = 15
# Cancelled / expired QR codes re-checked by the cron to catch late payments.
LATE_PAYMENT_WINDOW_MINUTES = 30


class PosAbaKhqrRequest(models.Model):
    _name = 'pos.aba.khqr.request'
    _description = 'ABA KHQR payment request (Point of Sale)'
    _order = 'id desc'
    _rec_name = 'tran_id'

    tran_id = fields.Char('Transaction ID', required=True, readonly=True, index=True, copy=False)
    mode = fields.Selection(
        [('payway', 'ABA PayWay'), ('bakong', 'Own KHQR')],
        required=True, readonly=True, default='payway')
    payment_method_id = fields.Many2one(
        'pos.payment.method', 'Payment Method', required=True, readonly=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    environment = fields.Selection(
        [('sandbox', 'Sandbox'), ('production', 'Production')], readonly=True)
    pos_config_id = fields.Many2one('pos.config', 'Point of Sale', readonly=True)
    pos_order_uuid = fields.Char('POS Order UUID', readonly=True, index=True)
    pos_reference = fields.Char('POS Reference', readonly=True)
    pos_order_id = fields.Many2one('pos.order', 'POS Order', readonly=True, ondelete='set null')
    pos_payment_id = fields.Many2one('pos.payment', 'POS Payment', readonly=True, ondelete='set null')
    currency_id = fields.Many2one('res.currency', 'Currency', required=True, readonly=True)
    amount = fields.Monetary('Amount', required=True, readonly=True)
    state = fields.Selection(
        [('pending', 'Waiting for payment'),
         ('paid', 'Paid'),
         ('cancelled', 'Cancelled'),
         ('expired', 'Expired'),
         ('failed', 'Failed')],
        default='pending', required=True, readonly=True, index=True)
    qr_string = fields.Text('KHQR String', readonly=True)
    qr_md5 = fields.Char('KHQR MD5', readonly=True, index=True)
    deeplink = fields.Char('ABA Mobile deeplink', readonly=True)
    expires_at = fields.Datetime('QR expires at', readonly=True)
    paid_at = fields.Datetime('Paid at', readonly=True)
    confirmed_by_id = fields.Many2one(
        'res.users', 'Confirmed by', readonly=True,
        help='Cashier who confirmed an own-KHQR payment by hand.')
    payway_status = fields.Char('PayWay status', readonly=True)
    payway_apv = fields.Char('APV', readonly=True, help='ABA approval code')
    payway_transaction_id = fields.Char('PayWay reference', readonly=True)
    paid_amount = fields.Float('Paid amount', readonly=True)
    paid_currency = fields.Char('Paid currency', readonly=True)
    amount_mismatch = fields.Boolean('Amount mismatch', readonly=True)
    late_payment = fields.Boolean(
        'Paid after cancel/expiry', readonly=True,
        help='ABA confirmed this payment after the cashier cancelled the QR or it '
             'expired, so the POS did not record it. Refund the customer or '
             'register the payment by hand.')
    last_check_at = fields.Datetime('Last status check', readonly=True)
    last_message = fields.Char('Last message', readonly=True)
    last_response = fields.Text('Last PayWay response', readonly=True)
    webhook_payload = fields.Text('Webhook payload', readonly=True)

    _sql_constraints = [
        ('tran_id_unique', 'unique(tran_id)', 'The KHQR transaction ID must be unique.'),
    ]

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    @api.model
    def _aba_khqr_new_tran_id(self):
        # PayWay limit: 20 characters. K + yymmddHHMMSS + 6 hex = 19.
        return 'K%s%s' % (fields.Datetime.now().strftime('%y%m%d%H%M%S'),
                          secrets.token_hex(3).upper())

    @api.model
    def _aba_khqr_ascii(self, text, limit=25):
        return re.sub(r'[^\x20-\x7E]', '', text or '').strip()[:limit]

    @api.model
    def _aba_khqr_create(self, method, config, amount, order_reference=None, order_uuid=None):
        currency = config.currency_id
        if currency.name not in khqr.CURRENCY_CODES:
            raise UserError(_('KHQR only supports USD and KHR, but this Point of Sale '
                              'uses %s.', currency.name))
        amount = currency.round(float(amount or 0.0))
        if float_compare(amount, 0.0, precision_rounding=currency.rounding) <= 0:
            raise UserError(_('KHQR can only receive money: the amount must be above zero.'))
        try:
            khqr.format_amount(amount, currency.name)  # validates KHR = whole riel
        except khqr.KHQRError as error:
            raise UserError(str(error)) from error
        # PayWay wants "1.00" for USD and "4000" for KHR
        amount_text = '%d' % amount if currency.name == 'KHR' else '%.2f' % amount

        lifetime = method.aba_khqr_lifetime or 5
        now = fields.Datetime.now()
        expires_at = now + timedelta(minutes=lifetime)
        tran_id = self._aba_khqr_new_tran_id()
        vals = {
            'tran_id': tran_id,
            'mode': method.aba_khqr_mode,
            'payment_method_id': method.id,
            'company_id': config.company_id.id,
            'pos_config_id': config.id,
            'pos_order_uuid': order_uuid or False,
            'pos_reference': (order_reference or '')[:64] or False,
            'currency_id': currency.id,
            'amount': amount,
            'expires_at': expires_at,
        }

        if method.aba_khqr_mode == 'payway':
            client = method._aba_khqr_payway_client()
            webhook = method.aba_khqr_webhook_url or ''
            callback = webhook if webhook.startswith('https://') else None
            try:
                try:
                    response = client.generate_qr(
                        tran_id, amount_text, currency.name, lifetime,
                        method.aba_khqr_template or 'template3_color',
                        callback_url=callback,
                    )
                except PayWayError as error:
                    if 'not enable' not in str(error).lower():
                        raise
                    # QR API not activated by ABA: get the KHQR through the
                    # Purchase API (the one the website checkout uses).
                    _logger.info('PayWay QR API disabled, using Purchase API for %s', tran_id)
                    response = client.purchase_khqr(
                        tran_id, amount_text, currency.name, lifetime, callback_url=callback)
            except PayWayError as error:
                _logger.warning('ABA PayWay KHQR failed for %s: %s', tran_id, error)
                raise UserError(_('ABA PayWay could not create the QR code:\n%s', error)) from error
            response.pop('qrImage', None)
            vals.update({
                'qr_string': response['qrString'],
                'deeplink': response.get('abapay_deeplink') or False,
                'environment': client.environment,
                'last_response': json.dumps(response)[:4000],
            })
        else:
            expires_ms = int(expires_at.replace(tzinfo=timezone.utc).timestamp() * 1000)
            try:
                vals['qr_string'] = khqr.from_source(
                    method.aba_khqr_source, currency.name, amount, expires_ms,
                    merchant_name=method.aba_khqr_merchant_name or self._aba_khqr_ascii(
                        method.company_id.name or config.company_id.name),
                    merchant_city=method.aba_khqr_merchant_city,
                    bill_number=self._aba_khqr_ascii(order_reference) or tran_id,
                    terminal_label=self._aba_khqr_ascii(config.name),
                )
            except khqr.KHQRError as error:
                raise UserError(_('Cannot build the KHQR: %s', error)) from error

        vals['qr_md5'] = khqr.md5(vals['qr_string'])
        return self.create(vals)

    # ------------------------------------------------------------------
    # Data sent to the POS
    # ------------------------------------------------------------------

    def _aba_khqr_qr_image(self):
        self.ensure_one()
        png = None
        if qrcode:
            try:
                qr = qrcode.QRCode(error_correction=ERROR_CORRECT_Q, box_size=10, border=2)
                qr.add_data(self.qr_string)
                qr.make(fit=True)
                buffer = io.BytesIO()
                qr.make_image(fill_color='black', back_color='white').save(buffer, format='PNG')
                png = buffer.getvalue()
            except Exception:  # noqa: BLE001 - fall back to Odoo's barcode engine
                _logger.exception('qrcode failed, falling back to reportlab')
        if png is None:
            png = self.env['ir.actions.report'].barcode(
                'QR', self.qr_string, width=600, height=600, barLevel='Q', quiet=0)
        return 'data:image/png;base64,' + base64.b64encode(png).decode()

    def _aba_khqr_merchant_name(self):
        try:
            return khqr.decode(self.qr_string or '', verify_crc=False).get('59') or ''
        except khqr.KHQRError:
            return ''

    def _aba_khqr_pos_data(self, with_image=False):
        self.ensure_one()
        now = fields.Datetime.now()
        expires_in = int((self.expires_at - now).total_seconds()) if self.expires_at else 0
        is_khr = self.currency_id.name == 'KHR'
        method = self.payment_method_id
        data = {
            'id': self.id,
            'tran_id': self.tran_id,
            'mode': self.mode,
            'state': self.state,
            'amount': self.amount,
            'amount_text': '{:,.0f}'.format(self.amount) if is_khr else '{:,.2f}'.format(self.amount),
            'currency': self.currency_id.name,
            'currency_symbol': '៛' if is_khr else '$',
            'merchant_name': self._aba_khqr_merchant_name(),
            'deeplink': self.deeplink or False,
            'expires_in': max(expires_in, 0),
            'apv': self.payway_apv or '',
            'message': self.last_message or '',
            'amount_mismatch': self.amount_mismatch,
            'logo_url': '/web/image/pos.payment.method/%s/image' % method.id if method.image else False,
        }
        if with_image and self.qr_string:
            data['qr_image'] = self._aba_khqr_qr_image()
        return data

    # ------------------------------------------------------------------
    # Status handling
    # ------------------------------------------------------------------

    def _aba_khqr_mark_paid(self, vals):
        self.ensure_one()
        previous_state = self.state
        vals.update({
            'state': 'paid',
            'paid_at': fields.Datetime.now(),
            'late_payment': previous_state != 'pending',
        })
        self.write(vals)
        if vals['late_payment']:
            _logger.warning('ABA KHQR %s was paid after it was %s.', self.tran_id, previous_state)

    def _aba_khqr_check_payway(self):
        """Ask PayWay for the status. Never trust the webhook body alone."""
        self.ensure_one()
        now = fields.Datetime.now()
        try:
            data = self.payment_method_id._aba_khqr_payway_client().check_transaction(self.tran_id)
        except (PayWayError, UserError) as error:
            self.write({'last_check_at': now, 'last_message': str(error)[:250]})
            return
        vals = {'last_check_at': now, 'last_response': json.dumps(data)[:4000]}
        status = data.get('status') or {}
        if not is_success(data):
            # code 6 "tran_id not found" simply means nobody paid yet.
            vals['last_message'] = str(status.get('message') or '')[:250]
            self.write(vals)
            return

        info = data.get('data') or {}
        try:
            code = int(info.get('payment_status_code'))
        except (TypeError, ValueError):
            code = None
        vals.update({
            'payway_status': info.get('payment_status') or False,
            'payway_apv': info.get('apv') or False,
            'payway_transaction_id': info.get('transaction_id') or status.get('tran_id') or False,
            'last_message': info.get('payment_status') or False,
        })
        if code == STATUS_APPROVED:
            merchant_amount = info.get('total_amount')
            if merchant_amount is None:
                merchant_amount = info.get('original_amount')
            vals.update({
                'paid_amount': info.get('payment_amount') or merchant_amount or 0.0,
                'paid_currency': info.get('payment_currency') or self.currency_id.name,
                'amount_mismatch': merchant_amount is not None and float_compare(
                    float(merchant_amount), self.amount,
                    precision_rounding=self.currency_id.rounding) != 0,
            })
            if self.state != 'paid':
                self._aba_khqr_mark_paid(vals)
                return
        elif code == STATUS_CANCELLED and self.state == 'pending':
            vals['state'] = 'failed'
        elif code in (STATUS_DECLINED, STATUS_REFUNDED):
            # A declined attempt can be retried by the customer: keep waiting.
            vals['last_message'] = _('ABA status: %s', info.get('payment_status') or code)
        self.write(vals)

    def _aba_khqr_refresh(self, force=False):
        now = fields.Datetime.now()
        for request in self.filtered(lambda r: r.state == 'pending'):
            if request.mode == 'payway':
                recent = request.last_check_at and (
                    now - request.last_check_at).total_seconds() < CHECK_THROTTLE_SECONDS
                if force or not recent:
                    request._aba_khqr_check_payway()
            if (request.state == 'pending' and request.expires_at
                    and now >= request.expires_at + timedelta(seconds=EXPIRY_GRACE_SECONDS)):
                request.write({
                    'state': 'expired',
                    'last_message': _('The QR code expired before it was paid.'),
                })

    def _aba_khqr_cancel(self):
        for request in self.filtered(lambda r: r.state == 'pending'):
            if request.mode == 'payway':
                # The customer may have paid a second before the cashier gave up.
                request._aba_khqr_check_payway()
                if request.state == 'paid':
                    continue
                try:
                    request.payment_method_id._aba_khqr_payway_client().close_transaction(request.tran_id)
                except (PayWayError, UserError) as error:
                    _logger.info('Could not close PayWay transaction %s: %s', request.tran_id, error)
            request.write({
                'state': 'cancelled',
                'last_message': _('Cancelled at the POS by %s', self.env.user.name),
            })

    def _aba_khqr_confirm_manual(self):
        self.ensure_one()
        if self.mode != 'bakong':
            raise UserError(_('ABA PayWay payments are confirmed automatically.'))
        if self.state == 'paid':
            return
        if self.state not in ('pending', 'expired'):
            raise UserError(_('This KHQR request is %s and cannot be confirmed.',
                              dict(self._fields['state'].selection)[self.state]))
        self.write({
            'state': 'paid',
            'paid_at': fields.Datetime.now(),
            'confirmed_by_id': self.env.uid,
            'paid_amount': self.amount,
            'paid_currency': self.currency_id.name,
            'last_message': _('Confirmed by %s after checking the bank app.', self.env.user.name),
        })

    @api.model
    def _aba_khqr_handle_webhook(self, payload, raw_body=''):
        tran_id = str(payload.get('tran_id') or payload.get('merchant_ref') or '').strip()
        if not tran_id:
            return False
        request = self.search([('tran_id', '=', tran_id), ('mode', '=', 'payway')], limit=1)
        if not request:
            _logger.info('ABA KHQR webhook for unknown tran_id %s', tran_id)
            return False
        request.webhook_payload = (raw_body or json.dumps(payload))[:4000]
        recent = request.last_check_at and (
            fields.Datetime.now() - request.last_check_at).total_seconds() < CHECK_THROTTLE_SECONDS
        if request.state != 'paid' and not recent:
            request._aba_khqr_check_payway()
        return True

    def action_aba_khqr_check(self):
        for request in self.sudo():
            if request.mode == 'payway':
                request._aba_khqr_check_payway()
            else:
                request._aba_khqr_refresh(force=True)
        return True

    @api.model
    def _cron_aba_khqr_sweep(self):
        now = fields.Datetime.now()
        stale = self.search([
            ('state', '=', 'pending'),
            ('expires_at', '<', now - timedelta(seconds=EXPIRY_GRACE_SECONDS)),
        ], limit=200)
        stale._aba_khqr_refresh(force=True)
        # A customer can still pay a cancelled QR until it expires: catch it.
        recent = self.search([
            ('mode', '=', 'payway'),
            ('state', 'in', ('cancelled', 'expired')),
            ('expires_at', '>=', now - timedelta(minutes=LATE_PAYMENT_WINDOW_MINUTES)),
        ], limit=200)
        for request in recent:
            request._aba_khqr_check_payway()
