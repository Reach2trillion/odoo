import time

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools import khqr
from ..tools.payway import MAX_LIFETIME, MIN_LIFETIME, PayWayClient, PayWayError

WEBHOOK_ROUTE = '/pos/aba_khqr/webhook'


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    aba_khqr_mode = fields.Selection(
        [('payway', 'ABA PayWay (confirmed automatically)'),
         ('bakong', 'My own KHQR (cashier confirms)')],
        string='KHQR source', default='payway',
        help='ABA PayWay: the QR comes from the PayWay QR API and the payment is '
             'confirmed automatically.\n'
             'My own KHQR: the QR is built from your ABA KHQR / Bakong ID; the '
             'cashier confirms once the money shows in the ABA app.')
    aba_khqr_provider_id = fields.Many2one(
        'payment.provider', string='ABA PayWay provider',
        domain=[('code', '=', 'aba_payway')],
        help='PayWay provider whose merchant ID and API key are used.')
    aba_khqr_lifetime = fields.Integer(
        'QR lifetime (minutes)', default=5,
        help='The QR stops working after this delay (PayWay minimum: 3 minutes).')
    aba_khqr_template = fields.Char(
        'QR image template', default='template3_color',
        help='PayWay "qr_image_template" parameter (required by the QR API).')
    aba_khqr_webhook_url = fields.Char('Webhook URL', compute='_compute_aba_khqr_webhook_url')
    aba_khqr_source = fields.Text(
        'Your KHQR text or Bakong ID',
        help='Scan your shop\'s ABA KHQR sticker with any QR reader (e.g. Google Lens), '
             'copy the text (it starts with 000201) and paste it here. You can also '
             'type a Bakong account ID such as name@bank.')
    aba_khqr_merchant_name = fields.Char(
        'Name shown to customers',
        help='Only used with a Bakong account ID (max 25 Latin characters). '
             'A pasted KHQR keeps the name registered at the bank.')
    aba_khqr_merchant_city = fields.Char('City', default='Phnom Penh')

    def _get_payment_terminal_selection(self):
        return super()._get_payment_terminal_selection() + [('aba_khqr', 'ABA KHQR')]

    @api.depends('use_payment_terminal')
    def _compute_aba_khqr_webhook_url(self):
        for method in self:
            method.aba_khqr_webhook_url = method.get_base_url() + WEBHOOK_ROUTE

    @api.onchange('use_payment_terminal', 'aba_khqr_mode')
    def _onchange_aba_khqr_provider(self):
        if (self.use_payment_terminal == 'aba_khqr' and self.aba_khqr_mode == 'payway'
                and not self.aba_khqr_provider_id):
            self.aba_khqr_provider_id = self.env['payment.provider'].search([
                ('code', '=', 'aba_payway'),
                ('company_id', 'in', (self.company_id or self.env.company).ids),
            ], limit=1)

    @api.constrains('use_payment_terminal', 'aba_khqr_mode', 'aba_khqr_provider_id',
                    'aba_khqr_lifetime', 'aba_khqr_source', 'aba_khqr_merchant_name',
                    'aba_khqr_merchant_city')
    def _check_aba_khqr_settings(self):
        for method in self.filtered(lambda m: m.use_payment_terminal == 'aba_khqr'):
            if not MIN_LIFETIME <= (method.aba_khqr_lifetime or 0) <= MAX_LIFETIME:
                raise ValidationError(_('The QR lifetime must be between %(min)s and %(max)s minutes.',
                                        min=MIN_LIFETIME, max=MAX_LIFETIME))
            if method.aba_khqr_mode == 'payway':
                if not method.aba_khqr_provider_id:
                    raise ValidationError(_('Choose the ABA PayWay provider for "%s".', method.name))
                continue
            try:
                khqr.from_source(
                    method.aba_khqr_source, 'USD', 1, int(time.time() * 1000) + 60000,
                    merchant_name=method.aba_khqr_merchant_name or self.env[
                        'pos.aba.khqr.request']._aba_khqr_ascii(method.company_id.name),
                    merchant_city=method.aba_khqr_merchant_city,
                )
            except khqr.KHQRError as error:
                raise ValidationError(_('Your KHQR settings are not valid: %s', error)) from error

    def _aba_khqr_payway_client(self):
        self.ensure_one()
        provider = self.aba_khqr_provider_id.sudo()
        if not provider:
            raise UserError(_('Choose the ABA PayWay provider on payment method "%s".', self.name))
        if 'payway_environment' in provider._fields:
            environment = provider.payway_environment
        else:
            environment = 'sandbox' if provider.state == 'test' else 'production'
        if provider.state == 'disabled' or environment not in ('production', 'sandbox'):
            raise UserError(_('The ABA PayWay provider "%s" is disabled.', provider.name))
        merchant_field = '%s_payway_merchant_id' % environment
        key_field = '%s_payway_key' % environment
        merchant_id = provider[merchant_field] if merchant_field in provider._fields else False
        api_key = provider[key_field] if key_field in provider._fields else False
        if not merchant_id or not api_key:
            raise UserError(_('Fill in the %(env)s merchant ID and API key on the ABA PayWay '
                              'provider "%(name)s".', env=environment, name=provider.name))
        try:
            return PayWayClient(merchant_id, api_key, environment)
        except PayWayError as error:
            raise UserError(str(error)) from error

    # ------------------------------------------------------------------
    # Called by the POS (see static/src/app/payment_aba_khqr.js)
    # ------------------------------------------------------------------

    def _aba_khqr_check_pos_access(self):
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_('Only Point of Sale users can take KHQR payments.'))
        self.ensure_one()
        if self.use_payment_terminal != 'aba_khqr':
            raise UserError(_('"%s" is not an ABA KHQR payment method.', self.name))

    def _aba_khqr_get_request(self, request_id):
        self._aba_khqr_check_pos_access()
        request = self.env['pos.aba.khqr.request'].sudo().browse(int(request_id)).exists()
        if not request or request.payment_method_id != self:
            raise UserError(_('Unknown KHQR payment request.'))
        return request

    def aba_khqr_create_request(self, config_id, amount, order_reference=None, order_uuid=None):
        self._aba_khqr_check_pos_access()
        config = self.env['pos.config'].browse(int(config_id)).exists()
        if not config or self not in config.payment_method_ids:
            raise UserError(_('"%s" is not enabled on this Point of Sale.', self.name))
        request = self.env['pos.aba.khqr.request'].sudo()._aba_khqr_create(
            self.sudo(), config, amount, order_reference, order_uuid)
        return request._aba_khqr_pos_data(with_image=True)

    def aba_khqr_check_request(self, request_id, force=False):
        request = self._aba_khqr_get_request(request_id)
        request._aba_khqr_refresh(force=bool(force))
        return request._aba_khqr_pos_data()

    def aba_khqr_cancel_request(self, request_id):
        request = self._aba_khqr_get_request(request_id)
        request._aba_khqr_cancel()
        return request._aba_khqr_pos_data()

    def aba_khqr_confirm_request(self, request_id):
        request = self._aba_khqr_get_request(request_id)
        request._aba_khqr_confirm_manual()
        return request._aba_khqr_pos_data()
