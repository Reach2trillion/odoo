# -*- coding: utf-8 -*-
import logging

import requests

from odoo import api, models

from .common import (
    FALLBACK_BOT_TOKEN_PARAM,
    FALLBACK_CHAT_ID_PARAM,
    PARAM_BOT_TOKEN,
    PARAM_CHAT_ID,
)

_logger = logging.getLogger(__name__)

TELEGRAM_SEND_MESSAGE_URL = 'https://api.telegram.org/bot%s/sendMessage'
REQUEST_TIMEOUT = 10  # seconds; the alert runs inside order confirmation


class SaleCodTelegram(models.AbstractModel):
    """Small helper around the Telegram Bot API and the module settings.

    Everything is read through ``sudo()`` so that stock users who validate a
    delivery (and have no access to settings) can still trigger the alert.
    """
    _name = 'sale.cod.telegram'
    _description = 'COD Telegram Alert Helper'

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    @api.model
    def _get_param(self, key, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(key, default)

    @api.model
    def _get_bool_param(self, key):
        value = self._get_param(key, False)
        return str(value or '').strip().lower() in ('true', '1', 'yes', 'on')

    @api.model
    def _get_bot_token(self):
        """Own token first, then the bot of the "Send by Telegram" module."""
        token = self._get_param(PARAM_BOT_TOKEN) or self._get_param(FALLBACK_BOT_TOKEN_PARAM) or ''
        return token.strip()

    @api.model
    def _get_chat_id(self, picking_type=None):
        """Chat to alert, in order of preference:

        1. the chat configured in this module's settings;
        2. the Telegram group of the delivery operation type, when the
           "Delivery Packing Telegram Notification" module is installed;
        3. that module's default group.
        """
        chat_id = (self._get_param(PARAM_CHAT_ID) or '').strip()
        if not chat_id and picking_type is not None and 'telegram_group_id' in picking_type._fields:
            chat_id = (picking_type.telegram_group_id or '').strip()
        if not chat_id:
            chat_id = (self._get_param(FALLBACK_CHAT_ID_PARAM) or '').strip()
        return chat_id

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    @api.model
    def _send_message(self, chat_id, text):
        """Send ``text`` (Telegram HTML) to ``chat_id``.

        Never raises: returns ``(True, '')`` on success and
        ``(False, error_message)`` otherwise, so callers can log the problem
        in the chatter without blocking the business flow.
        """
        token = self._get_bot_token()
        if not token:
            return False, 'Telegram bot token is not configured (COD Delivery Alert or Send by Telegram settings).'
        if not chat_id:
            return False, 'Telegram chat ID is not configured (COD Delivery Alert settings or delivery operation type).'

        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True,
        }
        try:
            response = requests.post(
                TELEGRAM_SEND_MESSAGE_URL % token, json=payload, timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            _logger.warning('COD Telegram alert: request failed: %s', exc)
            return False, str(exc)

        if response.ok:
            return True, ''

        try:
            description = response.json().get('description') or response.text
        except ValueError:
            description = response.text
        _logger.warning('COD Telegram alert: Telegram answered %s: %s', response.status_code, description)
        return False, 'HTTP %s: %s' % (response.status_code, description)
