# Part of the auth_telegram module. License LGPL-3.
import functools
import logging
import secrets

import requests

from odoo import api, models
from odoo.exceptions import AccessDenied
from odoo.http import request
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)

TELEGRAM_API = 'https://api.telegram.org/bot%s/%s'
TIMEOUT = 10

CALLBACK_PREFIX = 'tgl:'

# Chat messages, bilingual English / Khmer. Edit freely.
MSG_AUTH_REQUEST = (
    "🔐 <b>Authentication Request</b>\n"
    "🔐 <b>សំណើសុំការផ្ទៀងផ្ទាត់</b>\n\n"
    "App / កម្មវិធី: {company}\n"
    "Account / គណនី: {account}\n"
    "Username / ឈ្មោះអ្នកប្រើ: {username}\n"
    "Device / ឧបករណ៍: {device}\n"
    "IP: {ip}\n\n"
    "{question}\n\n"
    "⚠️ If you did not start this login on the website, tap Cancel.\n"
    "⚠️ បើអ្នកមិនបានចាប់ផ្តើមការចូលនេះទេ សូមចុច បោះបង់។\n"
    "⚠️ {company} will never ask you to approve a login or to share a code for someone else.\n"
    "⚠️ {company} នឹងមិនដែលស្នើឱ្យអ្នកយល់ព្រមការចូល ឬចែករំលែកលេខកូដជំនួសអ្នកដទៃឡើយ។"
)
QUESTION_LOGIN = (
    "Do you want to login to {company}?\n"
    "តើអ្នកចង់ចូលប្រើ {company} ទេ?"
)
QUESTION_LINK = (
    "Link this Telegram to the account <b>{login}</b>?\n"
    "ភ្ជាប់ Telegram នេះទៅគណនី <b>{login}</b>?"
)
QUESTION_CODE_HINT = (
    "After you tap Yes, I will send you a one-time code to type on the website.\n"
    "បន្ទាប់ពីអ្នកចុច យល់ព្រម ខ្ញុំនឹងផ្ញើលេខកូដមួយដងឱ្យអ្នកវាយបញ្ចូលនៅលើគេហទំព័រ។"
)
BTN_YES = "✅ Yes, Login / យល់ព្រម ចូល"
BTN_NO = "❌ Cancel / បោះបង់"
MSG_LOGIN_OK_BACK = (
    "✅ <b>Login Successful!</b>\n"
    "✅ <b>ចូលប្រើដោយជោគជ័យ!</b>\n\n"
    "Welcome back, {first}! 🎉\n"
    "សូមស្វាគមន៍ការត្រឡប់មកវិញ {first}! 🎉\n\n"
    "👈 Go back to the website: you are now signed in.\n"
    "👈 ត្រឡប់ទៅគេហទំព័រវិញ៖ អ្នកបានចូលប្រើរួចហើយ។"
)
MSG_LOGIN_OK_NEW = (
    "✅ <b>Login Successful!</b>\n"
    "✅ <b>ចូលប្រើដោយជោគជ័យ!</b>\n\n"
    "Welcome, {first}! 🎉\n"
    "សូមស្វាគមន៍ {first}! 🎉\n\n"
    "Your account has been created.\n"
    "គណនីរបស់អ្នកត្រូវបានបង្កើតដោយជោគជ័យ។\n\n"
    "👈 Go back to the website: you are now signed in.\n"
    "👈 ត្រឡប់ទៅគេហទំព័រវិញ៖ អ្នកបានចូលប្រើរួចហើយ។"
)
MSG_LINK_CONFIRMED = (
    "✅ <b>Confirmed!</b>\n"
    "✅ <b>បានបញ្ជាក់!</b>\n\n"
    "👈 Go back to the website to finish linking your Telegram to your {company} account, {first}.\n"
    "👈 ត្រឡប់ទៅគេហទំព័រវិញ ដើម្បីបញ្ចប់ការភ្ជាប់ Telegram ជាមួយគណនី {company} របស់អ្នក {first}។"
)
MSG_CODE = (
    "✅ <b>Confirmed!</b>\n"
    "✅ <b>បានបញ្ជាក់!</b>\n\n"
    "🔢 Your one-time code: <code>{code}</code>\n"
    "🔢 លេខកូដមួយដងរបស់អ្នក: <code>{code}</code>\n\n"
    "👈 Type it on the website where you started, to finish.\n"
    "👈 វាយបញ្ចូលវានៅលើគេហទំព័រដែលអ្នកបានចាប់ផ្តើម ដើម្បីបញ្ចប់។\n\n"
    "⚠️ Never share this code with anyone. {company} will never ask you for it.\n"
    "⚠️ កុំចែករំលែកលេខកូដនេះទៅនរណាម្នាក់ឡើយ។ {company} នឹងមិនដែលសួររកវាទេ។"
)
MSG_LINK_OK = (
    "✅ <b>Telegram account linked!</b>\n"
    "✅ <b>គណនី Telegram ត្រូវបានភ្ជាប់!</b>\n\n"
    "Your Telegram is now linked to your {company} account. You will receive your order updates here.\n"
    "Telegram របស់អ្នកត្រូវបានភ្ជាប់ជាមួយគណនី {company} របស់អ្នកហើយ។ អ្នកនឹងទទួលបានព័ត៌មានអំពីការបញ្ជាទិញនៅទីនេះ។"
)
MSG_CANCELLED = (
    "❌ Login cancelled.\n"
    "❌ ការចូលប្រើត្រូវបានបោះបង់។"
)
MSG_WRONG_CODE = (
    "❌ A wrong code was typed on the website too many times, so this login was cancelled. Please try again from the website.\n"
    "❌ លេខកូដខុសត្រូវបានវាយបញ្ចូលនៅលើគេហទំព័រច្រើនដងពេក ដូច្នេះការចូលប្រើនេះត្រូវបានបោះបង់។ សូមព្យាយាមម្តងទៀតពីគេហទំព័រ។"
)
MSG_EXPIRED = (
    "⚠️ This login link has expired. Please try again from the website.\n"
    "⚠️ តំណភ្ជាប់នេះផុតកំណត់ហើយ។ សូមព្យាយាមម្តងទៀតពីគេហទំព័រ។"
)
MSG_CONFLICT = (
    "⚠️ This login link was opened by another Telegram account, so it has been cancelled. Please start again from the website.\n"
    "⚠️ តំណភ្ជាប់នេះត្រូវបានបើកដោយគណនី Telegram ផ្សេងទៀត ដូច្នេះវាត្រូវបានបោះបង់។ សូមចាប់ផ្តើមម្តងទៀតពីគេហទំព័រ។"
)
MSG_NO_ACCOUNT = (
    "❌ No account is linked to this Telegram account and sign up is not allowed. Please contact us.\n"
    "❌ មិនមានគណនីភ្ជាប់ជាមួយ Telegram នេះទេ។ សូមទាក់ទងមកយើង។"
)
MSG_TAKEN = (
    "❌ This Telegram account is already linked to another user.\n"
    "❌ គណនី Telegram នេះត្រូវបានភ្ជាប់ជាមួយអ្នកប្រើផ្សេងទៀតរួចហើយ។"
)
MSG_UNLINKED = (
    "ℹ️ Your Telegram account has been unlinked from {company}. If this was not you, please contact us.\n"
    "ℹ️ គណនី Telegram របស់អ្នកត្រូវបានផ្តាច់ចេញពី {company}។ បើមិនមែនអ្នកទេ សូមទាក់ទងមកយើង។"
)
MSG_WELCOME = (
    "👋 Welcome to {company}!\n"
    "👋 សូមស្វាគមន៍មកកាន់ {company}!\n\n"
    "To log in, open {url} and tap “Log in with Telegram”.\n"
    "ដើម្បីចូលប្រើ សូមបើក {url} ហើយចុច “Log in with Telegram”។"
)
MSG_WELCOME_LINKED = (
    "👋 Hello {first}! Your Telegram is linked to your {company} account.\n"
    "👋 សួស្តី {first}! Telegram របស់អ្នកត្រូវបានភ្ជាប់ជាមួយគណនី {company} របស់អ្នក។\n\n"
    "You will receive your order updates here.\n"
    "អ្នកនឹងទទួលបានព័ត៌មានអំពីការបញ្ជាទិញរបស់អ្នកនៅទីនេះ។"
)
MSG_ASK_PHONE = (
    "📱 Please share your phone number so we can contact you about your orders.\n"
    "📱 សូមចែករំលែកលេខទូរស័ព្ទរបស់អ្នក ដើម្បីឱ្យយើងអាចទាក់ទងអ្នកអំពីការបញ្ជាទិញ។"
)
BTN_SHARE_PHONE = "📱 Share phone number / ចែករំលែកលេខទូរស័ព្ទ"
MSG_PHONE_SAVED = (
    "✅ Thank you! Your phone number has been saved.\n"
    "✅ អរគុណ! លេខទូរស័ព្ទរបស់អ្នកត្រូវបានរក្សាទុក។"
)


def _redact(exc, token):
    """ Exception text safe for the logs: requests/urllib3 connection errors
        embed the request path, i.e. the bot token. """
    text = '%s: %s' % (type(exc).__name__, exc)
    return text.replace(token, '<token>') if token else text


def _api_call(token, method, payload):
    """ Call a Bot API method. Returns the `result` or False, never raises. """
    try:
        response = requests.post(TELEGRAM_API % (token, method), json=payload, timeout=TIMEOUT)
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        # never log the exception object / traceback itself: it contains the token
        _logger.warning("Telegram API %s failed: %s", method, _redact(e, token))
        return False
    if not data.get('ok'):
        _logger.warning("Telegram API %s refused: %s", method, data.get('description'))
        return False
    return data.get('result', True)


def _message_payload(chat_id, text, reply_markup=None):
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML',
               'link_preview_options': {'is_disabled': True}}
    if reply_markup is not None:
        payload['reply_markup'] = reply_markup
    return payload


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


class TelegramBot(models.AbstractModel):
    """ Telegram Bot API client + handlers for the chat-based login flow. """
    _name = 'telegram.bot'
    _description = 'Telegram Bot'

    # ------------------------------------------------------------------
    # Bot API client
    # ------------------------------------------------------------------

    @api.model
    def _token(self):
        return self.env['ir.config_parameter'].sudo().get_param('auth_telegram.bot_token')

    @api.model
    def _api(self, method, **payload):
        """ Call a Bot API method. Returns the `result` or False, never raises. """
        token = self._token()
        if not token:
            return False
        return _api_call(token, method, payload)

    @api.model
    def _send_message(self, chat_id, text, reply_markup=None):
        if not chat_id:
            return False
        return self._api('sendMessage', **_message_payload(chat_id, text, reply_markup))

    @api.model
    def _send_message_after_commit(self, chat_id, text, reply_markup=None):
        """ Send the message once the current transaction is committed, so the
            user never reads about a state that was rolled back and never
            acts on it before the database reflects it. """
        token = self._token()
        if not token or not chat_id:
            return
        self.env.cr.postcommit.add(functools.partial(
            _api_call, token, 'sendMessage', _message_payload(chat_id, text, reply_markup)))

    # ------------------------------------------------------------------
    # Webhook management
    # ------------------------------------------------------------------

    @api.model
    def _base_url(self):
        """ Public base URL for links sent to Telegram and for the webhook:
            web.base.url when it is https (what the setup guide asks for),
            otherwise the origin of the current request when that is https,
            otherwise whichever of the two is set. """
        configured = (self.get_base_url() or '').rstrip('/')
        current = request.httprequest.url_root.rstrip('/') if request and request.httprequest else ''
        for url in (configured, current):
            if url.startswith('https://'):
                return url
        return configured or current

    @api.model
    def _webhook_url(self):
        return self._base_url() + '/auth/telegram/webhook'

    @api.model
    def _webhook_registered(self):
        """ Single source of truth for "the chat login can work": the last
            registration / status check saw Telegram pointing at *this*
            server's webhook URL, and the secret registered with it is still
            known. A secret alone is not enough: it is left in place when a
            later registration attempt fails (Telegram then still delivers
            to the old registration) and when the URL changed. """
        ICP = self.env['ir.config_parameter'].sudo()
        if not ICP.get_param('auth_telegram.webhook_secret'):
            return False
        status = ICP.get_param('auth_telegram.webhook_status') or ''
        expected = "Registered: %s" % self._webhook_url()
        # _check_webhook may append " — last error: ..." / " (N pending updates)"
        return status == expected or status.startswith(expected + ' ')

    @api.model
    def _set_webhook(self):
        """ Register the webhook with a fresh secret. Returns (ok, message);
            the outcome is also stored in the Status shown in Settings. """
        ICP = self.env['ir.config_parameter'].sudo()
        if not self._token():
            status = "Not registered: bot token is not configured"
            ICP.set_param('auth_telegram.webhook_status', status)
            return False, status
        url = self._webhook_url()
        if not url.startswith('https://'):
            status = ("Not registered: Telegram requires a public https:// URL "
                      "(web.base.url is currently %s)" % (self.get_base_url() or 'unset'))
            ICP.set_param('auth_telegram.webhook_status', status)
            return False, status
        secret = secrets.token_urlsafe(32)
        result = self._api('setWebhook', url=url, secret_token=secret,
                           allowed_updates=['message', 'callback_query'])
        if not result:
            status = "Registration failed: Telegram refused the webhook (see server log)"
            ICP.set_param('auth_telegram.webhook_status', status)
            return False, status
        ICP.set_param('auth_telegram.webhook_secret', secret)
        ICP.set_param('auth_telegram.webhook_status', "Registered: %s" % url)
        return True, url

    @api.model
    def _delete_webhook(self):
        ICP = self.env['ir.config_parameter'].sudo()
        self._api('deleteWebhook')
        ICP.set_param('auth_telegram.webhook_secret', False)
        ICP.set_param('auth_telegram.webhook_status', "Not registered")

    @api.model
    def _check_webhook(self):
        ICP = self.env['ir.config_parameter'].sudo()
        info = self._api('getWebhookInfo')
        if not info:
            status = "Could not reach Telegram (check bot token / server log)"
        elif not info.get('url'):
            status = "Not registered"
        elif info['url'] != self._webhook_url():
            # the login page hides the chat login while this status is stored
            # (see _webhook_registered); saving the settings re-registers
            status = ("Not registered here: Telegram sends updates to %s (this server expects %s). "
                      "Save or use Register Webhook." % (info['url'], self._webhook_url()))
        else:
            status = "Registered: %s" % info['url']
            if info.get('last_error_message'):
                status += " — last error: %s" % info['last_error_message']
            if info.get('pending_update_count'):
                status += " (%s pending updates)" % info['pending_update_count']
        ICP.set_param('auth_telegram.webhook_status', status)
        return status

    # ------------------------------------------------------------------
    # Update dispatch
    # ------------------------------------------------------------------

    @api.model
    def _handle_update(self, update):
        if not isinstance(update, dict):
            return
        callback = update.get('callback_query')
        message = update.get('message')
        if isinstance(callback, dict):
            self._handle_callback(callback)
        elif isinstance(message, dict) and isinstance(message.get('from'), dict) \
                and isinstance(message.get('chat'), dict):
            # the login flow only makes sense in the user's private chat
            if message['chat'].get('type', 'private') != 'private':
                return
            if isinstance(message.get('contact'), dict):
                self._handle_contact(message)
            else:
                text = message.get('text') or ''
                if text.startswith('/start'):
                    parts = text.split(maxsplit=1)
                    self._handle_start(message, parts[1].strip() if len(parts) > 1 else None)

    @api.model
    def _identity(self, tg_user):
        """ Normalize a Telegram `User` object into the validation dict used
            by res.users._auth_telegram_* """
        name = ' '.join(p for p in (tg_user.get('first_name'), tg_user.get('last_name')) if p)
        return {
            'id': str(tg_user['id']),
            'name': name or tg_user.get('username') or False,
            'username': tg_user.get('username') or False,
            'phone': False,
            'picture': False,
        }

    @api.model
    def _first_name(self, tg_user, fallback=''):
        return tg_user.get('first_name') or tg_user.get('username') or fallback

    @api.model
    def _match_code_enabled(self):
        return self.env['ir.config_parameter'].sudo().get_param('auth_telegram.bot_match_code') == '1'

    @api.model
    def _phone_request_enabled(self):
        return self.env['ir.config_parameter'].sudo().get_param('auth_telegram.bot_request_phone', '1') != '0'

    # ------------------------------------------------------------------
    # /start
    # ------------------------------------------------------------------

    @api.model
    def _handle_start(self, message, payload):
        tg_user = message['from']
        chat_id = message['chat']['id']
        company = html_escape(self.env.company.name)
        Users = self.env['res.users'].sudo()

        if not payload:
            user = Users.search([('telegram_uid', '=', str(tg_user['id']))], limit=1)
            if user:
                text = MSG_WELCOME_LINKED.format(first=html_escape(self._first_name(tg_user, user.name)),
                                                 company=company)
            else:
                text = MSG_WELCOME.format(company=company, url=html_escape(self._base_url()))
            self._send_message(chat_id, text)
            return

        login = self.env['auth.telegram.login'].sudo()._get_by_token(payload, states=('pending',))
        if not login:
            self._send_message(chat_id, MSG_EXPIRED)
            return
        login._lock()
        if login.state != 'pending':
            self._send_message(chat_id, MSG_EXPIRED)
            return

        identity = self._identity(tg_user)
        if login.telegram_uid and login.telegram_uid != identity['id']:
            # another Telegram account already opened this link (e.g. a
            # photographed QR code): fail closed so neither can complete it,
            # and tell both sides
            login._cancel('conflict')
            self._edit_buttons(login.telegram_chat_id, login.telegram_message_id)
            self._send_message_after_commit(login.telegram_chat_id, MSG_CONFLICT)
            self._send_message_after_commit(chat_id, MSG_CONFLICT)
            _logger.info("Telegram login: request %s claimed by Telegram uid %s was opened by uid %s, cancelled",
                         login.id, login.telegram_uid, identity['id'])
            return

        if login.link_user_id:
            account = login.link_user_id.name
            question = QUESTION_LINK.format(login=html_escape(login.link_user_id.login))
        else:
            existing = Users.search([('telegram_uid', '=', identity['id'])], limit=1)
            account = existing.name if existing else identity['name'] or '-'
            question = QUESTION_LOGIN.format(company=company)
        if login.match_code:
            question += "\n\n" + QUESTION_CODE_HINT

        login.write({
            'telegram_uid': identity['id'],
            'telegram_name': identity['name'] or False,
            'telegram_username': identity['username'] or False,
            'telegram_chat_id': str(chat_id),
        })
        text = MSG_AUTH_REQUEST.format(
            company=company,
            account=html_escape(account),
            username=html_escape('@%s' % identity['username']) if identity['username'] else '-',
            device=html_escape(login.requester_device or '-'),
            ip=html_escape(login.requester_ip or '-'),
            question=question,
        )
        rows = [[
            {'text': BTN_YES, 'callback_data': '%sy:%s' % (CALLBACK_PREFIX, login.token)},
            {'text': BTN_NO, 'callback_data': '%sn:%s' % (CALLBACK_PREFIX, login.token)},
        ]]
        sent = self._send_message(chat_id, text, reply_markup={'inline_keyboard': rows})
        if isinstance(sent, dict) and sent.get('message_id'):
            login.telegram_message_id = str(sent['message_id'])
        else:
            # Telegram did not acknowledge the prompt (unreachable, 429, bad
            # token...). The request stays pending: a read timeout can still
            # mean the prompt was delivered, and opening the deep link again
            # re-sends it. The website page is told (status poll) so it can
            # ask the user to tap Start again or retry, instead of waiting
            # for the request to expire.
            _logger.warning("Telegram login: request %s: prompt to chat %s not acknowledged by Telegram",
                            login.id, chat_id)

    # ------------------------------------------------------------------
    # Yes / Cancel buttons
    # ------------------------------------------------------------------

    @api.model
    def _handle_callback(self, callback):
        data = callback.get('data') or ''
        tg_user = callback.get('from') or {}
        message = callback.get('message') or {}
        chat = message.get('chat') or {}
        chat_id = chat.get('id')
        # a callback query must be answered exactly once, do it right away
        self._api('answerCallbackQuery', callback_query_id=callback.get('id'))
        if not data.startswith(CALLBACK_PREFIX) or not chat_id or 'id' not in tg_user:
            return
        if chat.get('type', 'private') != 'private':
            return
        parts = data[len(CALLBACK_PREFIX):].split(':')
        action = parts[0]
        token = parts[1] if len(parts) > 1 else ''

        login = self.env['auth.telegram.login'].sudo()._get_by_token(token)
        if login:
            login._lock()
            # only the Telegram user who sent /start may answer
            if login.telegram_uid != str(tg_user['id']):
                return
            if login.state in ('confirmed', 'done', 'cancelled'):
                # already answered (double tap, redelivered update): the first
                # handler removed the buttons and sent the outcome, stay silent
                return
        if not login or login.state != 'pending':
            self._edit_buttons(chat_id, message.get('message_id'))
            self._send_message(chat_id, MSG_EXPIRED)
            return

        self._edit_buttons(chat_id, message.get('message_id'))
        if action == 'y':
            self._confirm_login(login, tg_user, chat_id)
        elif action == 'n':
            login._cancel('user')
            self._send_message_after_commit(chat_id, MSG_CANCELLED)
        else:
            # button from a prompt sent by an older version of this module
            login._cancel('stale')
            self._send_message_after_commit(chat_id, MSG_EXPIRED)

    @api.model
    def _edit_buttons(self, chat_id, message_id, keyboard=None):
        if chat_id and message_id:
            self._api('editMessageReplyMarkup', chat_id=_as_int(chat_id), message_id=_as_int(message_id),
                      reply_markup=keyboard or {'inline_keyboard': []})

    @api.model
    def _confirm_login(self, login, tg_user, chat_id):
        Users = self.env['res.users'].sudo()
        identity = login._validation()
        company = html_escape(self.env.company.name)
        first = html_escape(self._first_name(tg_user, identity['name'] or ''))

        if login.link_user_id:
            # the Telegram account is only linked when the browser that
            # started the request completes it (/auth/telegram/complete),
            # after proving it belongs to that user's session
            existing = Users.with_context(active_test=False).search(
                [('telegram_uid', '=', identity['id'])], limit=1)
            if existing and existing.id != login.link_user_id.id:
                login._cancel('taken')
                self._send_message_after_commit(chat_id, MSG_TAKEN)
                return
            login.state = 'confirmed'
            if login.match_code:
                self._send_message_after_commit(chat_id, MSG_CODE.format(code=login.code, company=company))
            else:
                self._send_message_after_commit(chat_id, MSG_LINK_CONFIRMED.format(first=first, company=company))
            return

        existed = bool(Users.search([('telegram_uid', '=', identity['id'])], limit=1))
        identity['picture'], identity['picture_key'] = self._profile_photo(tg_user['id'])
        try:
            user = Users._auth_telegram_get_or_create_user(identity)
        except AccessDenied:
            login._cancel('no_account')
            self._send_message_after_commit(chat_id, MSG_NO_ACCOUNT)
            return
        login.write({'state': 'confirmed', 'user_id': user.id, 'user_created': not existed})
        if login.match_code:
            # the login is only granted once the browser that started the
            # request typed this code: the success message follows then
            self._send_message_after_commit(chat_id, MSG_CODE.format(code=login.code, company=company))
            return
        self._send_message_after_commit(chat_id, self._login_ok_text(login, first))
        self._ask_phone_after_commit(user, chat_id)

    @api.model
    def _login_ok_text(self, login, first):
        return (MSG_LOGIN_OK_NEW if login.user_created else MSG_LOGIN_OK_BACK).format(first=first)

    @api.model
    def _notify_login_done(self, login, user):
        """ Called by /auth/telegram/complete for a one-time code login: the
            code was typed, the user is signed in. """
        first = (login.telegram_name or '').split(' ')[0] or login.telegram_username or user.name
        self._send_message_after_commit(login.telegram_chat_id, self._login_ok_text(login, html_escape(first)))
        self._ask_phone_after_commit(user, login.telegram_chat_id)

    @api.model
    def _notify_wrong_code(self, login):
        """ Called when the website gave up on the one-time code. """
        self._send_message_after_commit(login.telegram_chat_id, MSG_WRONG_CODE)

    @api.model
    def _notify_linked(self, login, user):
        """ Called by /auth/telegram/complete once a link request is done. """
        company = html_escape(self.env.company.name)
        self._send_message_after_commit(login.telegram_chat_id, MSG_LINK_OK.format(company=company))
        self._ask_phone_after_commit(user, login.telegram_chat_id)

    @api.model
    def _notify_unlinked(self, chat_id):
        """ Tell a Telegram account it is no longer linked (unlink, or the
            user linked another Telegram account). """
        company = html_escape(self.env.company.name)
        self._send_message_after_commit(chat_id, MSG_UNLINKED.format(company=company))

    @api.model
    def _ask_phone_after_commit(self, user, chat_id):
        if self._phone_request_enabled() and not (user.partner_id.phone or user.partner_id.mobile):
            self._send_message_after_commit(chat_id, MSG_ASK_PHONE, reply_markup={
                'keyboard': [[{'text': BTN_SHARE_PHONE, 'request_contact': True}]],
                'resize_keyboard': True,
                'one_time_keyboard': True,
            })

    # ------------------------------------------------------------------
    # Shared contact (phone number)
    # ------------------------------------------------------------------

    @api.model
    def _handle_contact(self, message):
        contact = message['contact']
        tg_user = message['from']
        chat_id = message['chat']['id']
        # only accept the user's own number, not a forwarded contact
        if str(contact.get('user_id')) != str(tg_user['id']) or not contact.get('phone_number'):
            return
        user = self.env['res.users'].sudo().search([('telegram_uid', '=', str(tg_user['id']))], limit=1)
        if not user:
            return
        phone = contact['phone_number']
        if not phone.startswith('+'):
            phone = '+' + phone
        user.write({'telegram_phone': phone})
        if not user.partner_id.phone:
            user.partner_id.phone = phone
        self._send_message_after_commit(chat_id, MSG_PHONE_SAVED, reply_markup={'remove_keyboard': True})

    # ------------------------------------------------------------------
    # Profile photo
    # ------------------------------------------------------------------

    @api.model
    def _profile_photo(self, telegram_user_id):
        """ Return (download_url, stable_key) of the user's current profile
            photo, or (False, False). The download URL embeds the bot token,
            so only `stable_key` must ever be stored. """
        photos = self._api('getUserProfilePhotos', user_id=_as_int(telegram_user_id), limit=1)
        try:
            sizes = photos['photos'][0]
            best = sizes[-1]
            file_info = self._api('getFile', file_id=best['file_id'])
            file_path = file_info['file_path']
        except (KeyError, IndexError, TypeError):
            return False, False
        url = 'https://api.telegram.org/file/bot%s/%s' % (self._token(), file_path)
        return url, best.get('file_unique_id') or file_path
