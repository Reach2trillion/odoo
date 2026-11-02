# Part of the auth_telegram module. License LGPL-3.
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
    "Username / ឈ្មោះអ្នកប្រើ: {username}\n\n"
    "Do you want to login to {company}?\n"
    "តើអ្នកចង់ចូលប្រើ {company} ទេ?"
)
BTN_YES = "✅ Yes, Login / បាទ ចូល"
BTN_NO = "❌ Cancel / បោះបង់"
MSG_LOGIN_OK_BACK = (
    "✅ <b>Login Successful!</b>\n"
    "✅ <b>ចូលប្រើដោយជោគជ័យ!</b>\n\n"
    "Welcome back, {first}! 🎉\n"
    "សូមស្វាគមន៍ការត្រឡប់មកវិញ {first}! 🎉\n\n"
    "Your account has been successfully logged in.\n"
    "គណនីរបស់អ្នកត្រូវបានចូលប្រើដោយជោគជ័យ។\n\n"
    "👇 <b>Tap the button below to return to app</b>\n"
    "👇 ចុចប៊ូតុងខាងក្រោមដើម្បីត្រឡប់ទៅកម្មវិធី"
)
MSG_LOGIN_OK_NEW = (
    "✅ <b>Login Successful!</b>\n"
    "✅ <b>ចូលប្រើដោយជោគជ័យ!</b>\n\n"
    "Welcome, {first}! 🎉\n"
    "សូមស្វាគមន៍ {first}! 🎉\n\n"
    "Your account has been successfully created.\n"
    "គណនីរបស់អ្នកត្រូវបានបង្កើតដោយជោគជ័យ។\n\n"
    "👇 <b>Tap the button below to return to app</b>\n"
    "👇 ចុចប៊ូតុងខាងក្រោមដើម្បីត្រឡប់ទៅកម្មវិធី"
)
MSG_LINK_OK = (
    "✅ <b>Telegram account linked!</b>\n"
    "✅ <b>គណនី Telegram ត្រូវបានភ្ជាប់!</b>\n\n"
    "Your Telegram is now linked to your {company} account, {first}.\n"
    "Telegram របស់អ្នកត្រូវបានភ្ជាប់ជាមួយគណនី {company} របស់អ្នកហើយ {first}។\n\n"
    "👇 Tap the button below to return to app\n"
    "👇 ចុចប៊ូតុងខាងក្រោមដើម្បីត្រឡប់ទៅកម្មវិធី"
)
BTN_OPEN_APP = "🚀 Open App Automatically / បើកកម្មវិធីដោយស្វ័យប្រវត្តិ"
MSG_CANCELLED = (
    "❌ Login cancelled.\n"
    "❌ ការចូលប្រើត្រូវបានបោះបង់។"
)
MSG_EXPIRED = (
    "⚠️ This login link has expired. Please try again from the website.\n"
    "⚠️ តំណភ្ជាប់នេះផុតកំណត់ហើយ។ សូមព្យាយាមម្តងទៀតពីគេហទំព័រ។"
)
MSG_NO_ACCOUNT = (
    "❌ No account is linked to this Telegram account and sign up is not allowed. Please contact us.\n"
    "❌ មិនមានគណនីភ្ជាប់ជាមួយ Telegram នេះទេ។ សូមទាក់ទងមកយើង។"
)
MSG_TAKEN = (
    "❌ This Telegram account is already linked to another user.\n"
    "❌ គណនី Telegram នេះត្រូវបានភ្ជាប់ជាមួយអ្នកប្រើផ្សេងទៀតរួចហើយ។"
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
        try:
            response = requests.post(TELEGRAM_API % (token, method), json=payload, timeout=TIMEOUT)
            data = response.json()
        except (requests.RequestException, ValueError):
            _logger.warning("Telegram API %s failed", method, exc_info=True)
            return False
        if not data.get('ok'):
            _logger.warning("Telegram API %s refused: %s", method, data.get('description'))
            return False
        return data.get('result', True)

    @api.model
    def _send_message(self, chat_id, text, reply_markup=None):
        payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML',
                   'disable_web_page_preview': True}
        if reply_markup is not None:
            payload['reply_markup'] = reply_markup
        return self._api('sendMessage', **payload)

    # ------------------------------------------------------------------
    # Webhook management
    # ------------------------------------------------------------------

    @api.model
    def _base_url(self):
        """ Public base URL: the host of the current request when there is
            one (settings saved from the browser, Telegram calling the
            webhook), otherwise web.base.url. """
        if request and request.httprequest:
            return request.httprequest.url_root.rstrip('/')
        return (self.get_base_url() or '').rstrip('/')

    @api.model
    def _webhook_url(self):
        return self._base_url() + '/auth/telegram/webhook'

    @api.model
    def _set_webhook(self):
        """ Register the webhook with a fresh secret. Returns (ok, message). """
        ICP = self.env['ir.config_parameter'].sudo()
        if not self._token():
            return False, "Bot token is not configured"
        url = self._webhook_url()
        if not url.startswith('https://'):
            return False, "Telegram requires an https:// web.base.url (currently %s)" % url
        secret = secrets.token_urlsafe(32)
        result = self._api('setWebhook', url=url, secret_token=secret,
                           allowed_updates=['message', 'callback_query'])
        if not result:
            ICP.set_param('auth_telegram.webhook_status', "Registration failed, see server log")
            return False, "Telegram refused the webhook registration (see server log)"
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
            status = "Registered on another URL: %s" % info['url']
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
        elif isinstance(message, dict) and isinstance(message.get('from'), dict):
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

        identity = self._identity(tg_user)
        if login.link_user_id:
            account = login.link_user_id.name
        else:
            existing = Users.search([('telegram_uid', '=', identity['id'])], limit=1)
            account = existing.name if existing else identity['name'] or '-'
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
        )
        keyboard = {'inline_keyboard': [[
            {'text': BTN_YES, 'callback_data': '%sy:%s' % (CALLBACK_PREFIX, login.token)},
            {'text': BTN_NO, 'callback_data': '%sn:%s' % (CALLBACK_PREFIX, login.token)},
        ]]}
        sent = self._send_message(chat_id, text, reply_markup=keyboard)
        if isinstance(sent, dict) and sent.get('message_id'):
            login.telegram_message_id = str(sent['message_id'])

    # ------------------------------------------------------------------
    # Yes / Cancel buttons
    # ------------------------------------------------------------------

    @api.model
    def _handle_callback(self, callback):
        data = callback.get('data') or ''
        tg_user = callback.get('from') or {}
        message = callback.get('message') or {}
        chat_id = (message.get('chat') or {}).get('id')
        self._api('answerCallbackQuery', callback_query_id=callback.get('id'))
        if not data.startswith(CALLBACK_PREFIX) or not chat_id or 'id' not in tg_user:
            return
        action, _, token = data[len(CALLBACK_PREFIX):].partition(':')
        login = self.env['auth.telegram.login'].sudo()._get_by_token(token, states=('pending',))
        if not login:
            self._edit_buttons(chat_id, message.get('message_id'))
            self._send_message(chat_id, MSG_EXPIRED)
            return
        # only the Telegram user who sent /start may answer
        if login.telegram_uid != str(tg_user['id']):
            return
        self._edit_buttons(chat_id, message.get('message_id'))
        if action != 'y':
            login.state = 'cancelled'
            self._send_message(chat_id, MSG_CANCELLED)
            return
        self._confirm_login(login, tg_user, chat_id)

    @api.model
    def _edit_buttons(self, chat_id, message_id, keyboard=None):
        if message_id:
            self._api('editMessageReplyMarkup', chat_id=chat_id, message_id=message_id,
                      reply_markup=keyboard or {'inline_keyboard': []})

    @api.model
    def _confirm_login(self, login, tg_user, chat_id):
        Users = self.env['res.users'].sudo()
        identity = login._validation()
        identity['picture'], identity['picture_key'] = self._profile_photo(tg_user['id'])
        company = html_escape(self.env.company.name)
        first = html_escape(self._first_name(tg_user, identity['name'] or ''))
        open_url = '%s/auth/telegram/complete?token=%s' % (self._base_url(), login.token)
        open_button = {'inline_keyboard': [[{'text': BTN_OPEN_APP, 'url': open_url}]]}

        if login.link_user_id:
            user = Users._auth_telegram_link(login.link_user_id.id, identity)
            if not user:
                login.state = 'cancelled'
                self._send_message(chat_id, MSG_TAKEN)
                return
            login.write({'state': 'confirmed', 'user_id': user.id})
            self._send_message(chat_id, MSG_LINK_OK.format(first=first, company=company),
                               reply_markup=open_button)
        else:
            existed = bool(Users.search([('telegram_uid', '=', identity['id'])], limit=1))
            try:
                user = Users._auth_telegram_get_or_create_user(identity)
            except AccessDenied:
                login.state = 'cancelled'
                self._send_message(chat_id, MSG_NO_ACCOUNT)
                return
            login.write({'state': 'confirmed', 'user_id': user.id, 'user_created': not existed})
            text = (MSG_LOGIN_OK_BACK if existed else MSG_LOGIN_OK_NEW).format(first=first)
            self._send_message(chat_id, text, reply_markup=open_button)

        if self._phone_request_enabled() and not (user.partner_id.phone or user.partner_id.mobile):
            self._send_message(chat_id, MSG_ASK_PHONE, reply_markup={
                'keyboard': [[{'text': BTN_SHARE_PHONE, 'request_contact': True}]],
                'resize_keyboard': True,
                'one_time_keyboard': True,
            })

    @api.model
    def _phone_request_enabled(self):
        return self.env['ir.config_parameter'].sudo().get_param('auth_telegram.bot_request_phone', '1') != '0'

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
        self._send_message(chat_id, MSG_PHONE_SAVED, reply_markup={'remove_keyboard': True})

    # ------------------------------------------------------------------
    # Profile photo
    # ------------------------------------------------------------------

    @api.model
    def _profile_photo(self, telegram_user_id):
        """ Return (download_url, stable_key) of the user's current profile
            photo, or (False, False). The download URL embeds the bot token,
            so only `stable_key` must ever be stored. """
        photos = self._api('getUserProfilePhotos', user_id=telegram_user_id, limit=1)
        try:
            sizes = photos['photos'][0]
            best = sizes[-1]
            file_info = self._api('getFile', file_id=best['file_id'])
            file_path = file_info['file_path']
        except (KeyError, IndexError, TypeError):
            return False, False
        url = 'https://api.telegram.org/file/bot%s/%s' % (self._token(), file_path)
        return url, best.get('file_unique_id') or file_path
