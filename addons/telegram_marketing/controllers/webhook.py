# -*- coding: utf-8 -*-
import hmac
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class TelegramWebhookController(http.Controller):

    @http.route('/telegram/webhook/<int:bot_id>/<string:secret>', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
    def telegram_webhook(self, bot_id, secret, **kwargs):
        """Receive updates pushed by Telegram (set with setWebhook).

        Always answers 200 once the bot is identified: otherwise Telegram keeps retrying the same
        update forever. Processing errors are logged and the update is dropped.
        """
        bot = request.env['telegram.bot'].sudo().browse(bot_id).exists()
        expected = (bot.webhook_secret or '') if bot else ''
        if not bot or not expected or not hmac.compare_digest(expected, secret or ''):
            return request.make_json_response({'ok': False, 'error': 'unknown bot'}, status=403)
        header_secret = request.httprequest.headers.get('X-Telegram-Bot-Api-Secret-Token')
        if header_secret is not None and not hmac.compare_digest(expected, header_secret):
            return request.make_json_response({'ok': False, 'error': 'bad secret token'}, status=403)

        try:
            update = json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except ValueError:
            return request.make_json_response({'ok': False, 'error': 'invalid json'}, status=400)
        if not isinstance(update, dict):
            return request.make_json_response({'ok': False, 'error': 'invalid update'}, status=400)

        try:
            bot._process_update(update)
        except Exception:  # noqa: BLE001 - never let Telegram retry forever
            _logger.exception("Telegram webhook: error while processing update %s for bot %s",
                              update.get('update_id'), bot_id)
            request.env.cr.rollback()
        return request.make_json_response({'ok': True})
