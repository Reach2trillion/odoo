# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ChatflowController(http.Controller):
    """Facebook Messenger webhook endpoint.

    The POST handler only queues the raw payload and answers immediately:
    Facebook retries (and eventually disables) webhooks that answer
    slowly, so all processing happens asynchronously in a triggered cron.
    """

    @http.route('/chatflow/webhook', type='http', auth='public',
                methods=['GET'], csrf=False)
    def webhook_verify(self, **kwargs):
        args = request.httprequest.args
        mode = args.get('hub.mode')
        token = args.get('hub.verify_token')
        challenge = args.get('hub.challenge', '')
        pages = request.env['chatflow.page'].sudo().search([])
        if mode == 'subscribe' and token and token in {
                page.verify_token for page in pages if page.verify_token}:
            return request.make_response(
                challenge, headers=[('Content-Type', 'text/plain')])
        return request.make_response('Verification token mismatch',
                                     status=403)

    @http.route('/chatflow/webhook', type='http', auth='public',
                methods=['POST'], csrf=False)
    def webhook_receive(self, **kwargs):
        raw_body = request.httprequest.get_data()
        signature = request.httprequest.headers.get(
            'X-Hub-Signature-256', '')
        Page = request.env['chatflow.page'].sudo()
        if not Page._verify_webhook_signature(raw_body, signature):
            _logger.warning(
                "chatflow: rejected webhook call with bad signature")
            return request.make_response('Invalid signature', status=403)
        try:
            payload = json.loads(raw_body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            payload = {}
        if payload.get('object') in ('page', 'instagram'):
            request.env['chatflow.event'].sudo().create({
                'payload': json.dumps(payload, ensure_ascii=False),
            })
            request.env.ref('chatflow.ir_cron_process_events').sudo()._trigger()
        return request.make_response(
            'EVENT_RECEIVED', headers=[('Content-Type', 'text/plain')])
