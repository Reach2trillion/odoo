# -*- coding: utf-8 -*-
import json
from unittest.mock import patch

from odoo.tests import HttpCase, tagged

from .common import FakeTelegramApi


@tagged('post_install', '-at_install', 'telegram')
class TestTelegramWebhook(HttpCase):

    def setUp(self):
        super().setUp()
        self.api = FakeTelegramApi()
        post_patcher = patch('requests.post', side_effect=self.api.post)
        post_patcher.start()
        self.addCleanup(post_patcher.stop)
        self.bot = self.env['telegram.bot'].create({
            'name': 'Webhook Bot',
            'token': '111222333:WEBHOOKTOKEN_abcdefghijklmnopqrstuvwxyz',
            'state': 'connected',
            'username': 'webhook_bot',
            'welcome_body': '<p>Welcome!</p>',
        })

    def _post(self, secret, payload, header_secret=None):
        headers = {'Content-Type': 'application/json'}
        if header_secret is not None:
            headers['X-Telegram-Bot-Api-Secret-Token'] = header_secret
        return self.url_open('/telegram/webhook/%s/%s' % (self.bot.id, secret), data=json.dumps(payload), headers=headers)

    def _update(self, text):
        return {
            'update_id': 900001,
            'message': {
                'message_id': 1, 'date': 1700000000,
                'from': {'id': 4242, 'is_bot': False, 'first_name': 'Web', 'username': 'webuser'},
                'chat': {'id': 4242, 'type': 'private', 'first_name': 'Web', 'username': 'webuser'},
                'text': text,
            },
        }

    def test_webhook_accepts_update(self):
        response = self._post(self.bot.webhook_secret, self._update('/start'), header_secret=self.bot.webhook_secret)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True})
        chat = self.env['telegram.chat'].search([('bot_id', '=', self.bot.id), ('chat_id', '=', '4242')])
        self.assertEqual(len(chat), 1)
        self.assertEqual(chat.telegram_message_ids.sorted('id').mapped('direction'), ['in', 'out'])
        self.assertEqual(self.api.sent()[0]['params']['text'], 'Welcome!')

    def test_webhook_rejects_wrong_secret(self):
        response = self._post('wrong-secret', self._update('hello'))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.env['telegram.chat'].search([('bot_id', '=', self.bot.id)]))

    def test_webhook_rejects_wrong_header_token(self):
        response = self._post(self.bot.webhook_secret, self._update('hello'), header_secret='tampered')
        self.assertEqual(response.status_code, 403)

    def test_webhook_rejects_invalid_json(self):
        response = self.url_open('/telegram/webhook/%s/%s' % (self.bot.id, self.bot.webhook_secret),
                                 data='not json', headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 400)

    def test_webhook_unknown_bot(self):
        response = self.url_open('/telegram/webhook/999999/whatever', data='{}', headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 403)
