import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class AbaKhqrWebhookController(http.Controller):

    @http.route('/pos/aba_khqr/webhook', type='http', auth='public', methods=['POST'],
                csrf=False, save_session=False)
    def aba_khqr_webhook(self, **post):
        """PayWay push-back. The body only tells us *which* QR to re-check:
        the status itself is always fetched from PayWay (check-transaction-2)."""
        raw_body = request.httprequest.get_data(as_text=True) or ''
        payload = {}
        if raw_body.lstrip().startswith('{'):
            try:
                payload = json.loads(raw_body)
            except ValueError:
                _logger.info('ABA KHQR webhook: unreadable JSON body')
        if not isinstance(payload, dict) or not payload:
            payload = dict(post)
        request.env['pos.aba.khqr.request'].sudo()._aba_khqr_handle_webhook(payload, raw_body)
        return request.make_json_response({'status': 'ok'})
