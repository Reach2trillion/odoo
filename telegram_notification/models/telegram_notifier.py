# Part of the telegram_notification module. License LGPL-3.
import logging

import requests

from odoo import api, models

_logger = logging.getLogger(__name__)

TELEGRAM_SEND_URL = 'https://api.telegram.org/bot%s/sendMessage'
TIMEOUT = 10

NOTIFICATION_EVENTS = ('quotation', 'order', 'delivery', 'invoice')


class TelegramNotifier(models.AbstractModel):
    _name = 'telegram.notifier'
    _description = 'Telegram Notifications'

    @api.model
    def _event_enabled(self, event):
        ICP = self.env['ir.config_parameter'].sudo()
        if not ICP.get_param('auth_telegram.bot_token'):
            return False
        return ICP.get_param('telegram_notification.%s' % event, '1') != '0'

    @api.model
    def _notify_partner(self, partner, body, event):
        """ Send `body` (Telegram HTML) to the Telegram account linked to
            `partner`. Best effort: the message goes out after the current
            transaction commits, and failures only produce a log entry —
            business flows (order confirmation, invoicing...) are never
            blocked by Telegram being unreachable.
            :return: whether a message was scheduled
        """
        try:
            if event not in NOTIFICATION_EVENTS or not self._event_enabled(event):
                return False
            chat_id = partner and partner._telegram_chat_id()
            if not chat_id:
                return False
            token = self.env['ir.config_parameter'].sudo().get_param('auth_telegram.bot_token')
            # in a private conversation the chat id is the Telegram user id;
            # send post-commit so a rollback cannot produce ghost messages
            self.env.cr.postcommit.add(lambda: self._send_message(token, chat_id, body))
            return True
        except Exception:
            _logger.warning("Could not schedule Telegram notification for partner %s",
                            partner and partner.id, exc_info=True)
            return False

    @staticmethod
    def _send_message(token, chat_id, body):
        try:
            response = requests.post(TELEGRAM_SEND_URL % token, json={
                'chat_id': chat_id,
                'text': body,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True,
            }, timeout=TIMEOUT)
            if not response.ok:
                # 403 means the user never allowed the bot to message them
                _logger.warning("Telegram sendMessage to chat %s failed: %s",
                                chat_id, response.text[:300])
        except Exception:
            _logger.warning("Telegram sendMessage to chat %s errored", chat_id, exc_info=True)
