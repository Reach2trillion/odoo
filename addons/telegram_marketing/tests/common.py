# -*- coding: utf-8 -*-
import base64
from unittest.mock import patch

import requests

from odoo.tests import TransactionCase

# 1x1 transparent PNG
TINY_PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')


class FakeResponse:
    def __init__(self, payload=None, status_code=200, content=b''):
        self._payload = payload
        self.status_code = status_code
        self.content = content

    def json(self):
        if self._payload is None:
            raise ValueError('No JSON body')
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError('HTTP %s' % self.status_code)


class FakeTelegramApi:
    """In-memory stand-in for api.telegram.org."""

    def __init__(self):
        self.calls = []
        self.next_message_id = 1000
        self.failures = {}            # chat_id (str) -> (error_code, description)
        self.rate_limit_remaining = 0  # number of send calls answered with 429
        self.updates = []             # answered by getUpdates
        self.file_content = TINY_PNG
        self.chat_info = {}           # identifier -> chat dict answered by getChat

    # -- requests replacements -------------------------------------------------
    def post(self, url, json=None, data=None, files=None, timeout=None):
        method = url.rsplit('/', 1)[-1]
        params = dict(json or data or {})
        self.calls.append({'method': method, 'params': params, 'files': files, 'url': url})
        return FakeResponse(self._handle(method, params))

    def get(self, url, timeout=None):
        self.calls.append({'method': 'download', 'params': {}, 'files': None, 'url': url})
        return FakeResponse(content=self.file_content)

    # -- helpers -----------------------------------------------------------------
    @staticmethod
    def _ok(result):
        return {'ok': True, 'result': result}

    @staticmethod
    def _error(code, description, parameters=None):
        payload = {'ok': False, 'error_code': code, 'description': description}
        if parameters:
            payload['parameters'] = parameters
        return payload

    def _handle(self, method, params):
        if method == 'getMe':
            return self._ok({'id': 777, 'is_bot': True, 'first_name': 'Test Bot', 'username': 'abj_test_bot'})
        if method in ('setWebhook', 'deleteWebhook'):
            return self._ok(True)
        if method == 'getWebhookInfo':
            return self._ok({'url': 'https://example.com/telegram/webhook/1/x', 'pending_update_count': 0})
        if method == 'getChat':
            info = self.chat_info.get(str(params.get('chat_id')))
            return self._ok(info) if info else self._error(400, 'Bad Request: chat not found')
        if method == 'getUpdates':
            updates, self.updates = self.updates, []
            return self._ok(updates)
        if method == 'getFile':
            return self._ok({'file_id': params.get('file_id'), 'file_path': 'photos/file_1.jpg', 'file_size': len(self.file_content)})
        if method in ('sendMessage', 'sendPhoto', 'sendDocument'):
            if self.rate_limit_remaining > 0:
                self.rate_limit_remaining -= 1
                return self._error(429, 'Too Many Requests: retry after 3', {'retry_after': 3})
            chat_id = str(params.get('chat_id'))
            if chat_id in self.failures:
                code, description = self.failures[chat_id]
                return self._error(code, description)
            self.next_message_id += 1
            return self._ok({'message_id': self.next_message_id, 'chat': {'id': chat_id}})
        return self._error(404, 'Not Found: %s' % method)

    def sent(self, method=None):
        methods = (method,) if method else ('sendMessage', 'sendPhoto', 'sendDocument')
        return [call for call in self.calls if call['method'] in methods]


class TelegramCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.bot = cls.env['telegram.bot'].create({
            'name': 'Test Bot',
            'token': '123456789:TESTTOKEN_abcdefghijklmnopqrstuvwxyz',
            'state': 'connected',
            'username': 'abj_test_bot',
            'welcome_body': '<p>Welcome {{ object.first_name ||| friend }}!</p>',
            'stop_body': '<p>Bye</p>',
        })
        cls.tag_vip = cls.env['telegram.chat.tag'].create({'name': 'Test VIP'})
        cls.chat_alice = cls.env['telegram.chat'].create({
            'bot_id': cls.bot.id, 'chat_id': '1001', 'first_name': 'Alice', 'username': 'alice',
            'tag_ids': [(6, 0, [cls.tag_vip.id])],
        })
        cls.chat_bob = cls.env['telegram.chat'].create({
            'bot_id': cls.bot.id, 'chat_id': '1002', 'first_name': 'Bob',
        })
        cls.chat_group = cls.env['telegram.chat'].create({
            'bot_id': cls.bot.id, 'chat_id': '-100500', 'chat_type': 'supergroup', 'title': 'ABJ Customers',
        })
        cls.user_marketing = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Marketing User',
            'login': 'telegram_marketing_user',
            'email': 'marketing@example.com',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.env.ref('telegram_marketing.group_telegram_user').id])],
        })

    def setUp(self):
        super().setUp()
        self.api = FakeTelegramApi()
        post_patcher = patch('requests.post', side_effect=self.api.post)
        get_patcher = patch('requests.get', side_effect=self.api.get)
        post_patcher.start()
        get_patcher.start()
        self.addCleanup(post_patcher.stop)
        self.addCleanup(get_patcher.stop)

    # -- update builders -----------------------------------------------------------
    _update_counter = 5000

    @classmethod
    def _next_update_id(cls):
        cls._update_counter += 1
        return cls._update_counter

    def make_message_update(self, chat_id, text=None, first_name='Alice', last_name=None, username='alice',
                            chat_type='private', title=None, message_id=None, is_bot=False, **extra):
        self.__class__._message_counter = getattr(self.__class__, '_message_counter', 100) + 1
        user = {'id': abs(int(chat_id)) if str(chat_id).lstrip('-').isdigit() else 1, 'is_bot': is_bot,
                'first_name': first_name, 'language_code': 'km'}
        if last_name:
            user['last_name'] = last_name
        if username:
            user['username'] = username
        chat = {'id': int(chat_id), 'type': chat_type}
        if chat_type == 'private':
            chat.update({'first_name': first_name, 'last_name': last_name, 'username': username})
            chat = {key: value for key, value in chat.items() if value}
        else:
            chat['title'] = title or 'Group'
        message = {
            'message_id': message_id or self.__class__._message_counter,
            'from': user,
            'chat': chat,
            'date': 1700000000,
        }
        if text is not None:
            message['text'] = text
        message.update(extra)
        return {'update_id': self._next_update_id(), 'message': message}

    def make_chat_member_update(self, chat_id, status, chat_type='private', first_name='Alice', username='alice'):
        chat = {'id': int(chat_id), 'type': chat_type}
        if chat_type == 'private':
            chat.update({'first_name': first_name, 'username': username})
        else:
            chat['title'] = 'Group'
        return {
            'update_id': self._next_update_id(),
            'my_chat_member': {
                'chat': chat,
                'from': {'id': abs(int(chat_id)), 'is_bot': False, 'first_name': first_name},
                'date': 1700000000,
                'old_chat_member': {'user': {'id': 777, 'is_bot': True, 'first_name': 'Test Bot'}, 'status': 'member'},
                'new_chat_member': {'user': {'id': 777, 'is_bot': True, 'first_name': 'Test Bot'}, 'status': status},
            },
        }
