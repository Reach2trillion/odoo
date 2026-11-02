# Part of the auth_telegram module. License LGPL-3.
import base64
import hashlib
import logging
import secrets
import time
from urllib.parse import quote as urlquote, urlencode, urljoin

from odoo import api, http, SUPERUSER_ID, _
from odoo.exceptions import AccessDenied
from odoo.http import request
from odoo.modules.registry import Registry
from odoo.tools import email_normalize
from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.utils import ensure_db
try:
    from odoo.addons.web.controllers.utils import _get_login_redirect_url
except ImportError:  # pragma: no cover
    _get_login_redirect_url = None

_logger = logging.getLogger(__name__)

# session key holding the token of the chat-login request started by this browser
SESSION_LOGIN_KEY = 'auth_telegram_login'
# a password re-check (same window as Odoo's own check_identity) is required
# before a user changes which Telegram account can sign in to their account
IDENTITY_CHECK_VALIDITY = 10 * 60


def _telegram_error_message(code):
    return {
        'validation': _("Your Telegram sign in could not be verified. Please try again."),
        'no-account': _("No account is linked to this Telegram account, and sign up is not allowed."),
        'session': _("Please finish the Telegram login in the browser where you started it."),
    }.get(code, _("Telegram sign in failed. Please try again."))


def _telegram_callback_uri():
    return urljoin(request.httprequest.url_root, '/auth/telegram/callback')


def _device_label(user_agent):
    """ Short "Chrome · Android" style label shown in the Telegram prompt. """
    ua = user_agent or ''
    if 'Android' in ua:
        platform = 'Android'
    elif 'iPhone' in ua or 'iPad' in ua:
        platform = 'iPhone/iPad'
    elif 'Windows' in ua:
        platform = 'Windows'
    elif 'Macintosh' in ua or 'Mac OS' in ua:
        platform = 'Mac'
    elif 'Linux' in ua:
        platform = 'Linux'
    else:
        platform = ''
    if 'Edg/' in ua:
        browser = 'Edge'
    elif 'OPR/' in ua or 'Opera' in ua:
        browser = 'Opera'
    elif 'Firefox/' in ua or 'FxiOS/' in ua:
        browser = 'Firefox'
    elif 'Chrome/' in ua or 'CriOS/' in ua:
        browser = 'Chrome'
    elif 'Safari/' in ua:
        browser = 'Safari'
    else:
        browser = ''
    return ' · '.join(filter(None, (browser, platform))) or 'Unknown device'


class TelegramAuthHome(Home):

    @http.route()
    def web_login(self, *args, **kw):
        response = super().web_login(*args, **kw)
        if getattr(response, 'is_qweb', False):
            response.qcontext.update(self._auth_telegram_login_qcontext())
        return response

    def _auth_telegram_login_qcontext(self):
        values = {}
        mode = request.env['res.users'].sudo()._auth_telegram_mode()
        redirect = request.params.get('redirect')
        if mode in ('bot', 'oidc'):
            login_url = '/auth/telegram/login'
            if redirect:
                login_url = '%s?%s' % (login_url, urlencode({'redirect': redirect}))
            values['telegram_login_url'] = login_url
        elif mode == 'widget':
            bot_username = request.env['ir.config_parameter'].sudo().get_param('auth_telegram.bot_username')
            auth_url = _telegram_callback_uri()
            if redirect:
                auth_url = '%s?%s' % (auth_url, urlencode({'redirect': redirect}))
            values.update(telegram_bot_username=bot_username, telegram_auth_url=auth_url)
        error_code = request.params.get('telegram_error')
        if error_code:
            values['error'] = _telegram_error_message(error_code)
        return values


class TelegramAuthController(http.Controller):

    # ------------------------------------------------------------------
    # entry point: chat flow or OpenID Connect
    # ------------------------------------------------------------------

    # website=True / multilang=False like auth_totp's /web/login/totp: the page
    # uses web.login_layout, which the website module renders inside
    # website.layout, and that only works on a frontend route
    @http.route('/auth/telegram/login', type='http', auth='public', methods=['GET'],
                website=True, multilang=False, sitemap=False)
    def telegram_login_start(self, redirect=None, link=None, **kw):
        """ Start a Telegram login: the bot chat flow or the OpenID Connect
            authorization code flow (with PKCE). With `link`, the flow links
            the Telegram account to the already logged-in user instead of
            signing in. """
        Users = request.env['res.users'].sudo()
        mode = Users._auth_telegram_mode()
        if mode not in ('bot', 'oidc'):
            return request.redirect('/web/login')
        if link:
            if not request.session.uid:
                return request.redirect('/web/login?redirect=%s' % urlquote('/auth/telegram/link'))
            if not self._telegram_identity_checked():
                return request.redirect('/auth/telegram/link')
        if mode == 'bot':
            return self._telegram_bot_login_start(redirect, link)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(16)
        request.session['telegram_oauth'] = {
            'state': state,
            'verifier': verifier,
            'nonce': nonce,
            'redirect': redirect or False,
            'link_uid': request.session.uid if link else False,
        }
        url = Users._auth_telegram_oidc_authorize_url(
            _telegram_callback_uri(), state, nonce, challenge)
        return request.redirect(url, local=False)

    # ------------------------------------------------------------------
    # bot chat flow (/start in Telegram)
    # ------------------------------------------------------------------

    def _telegram_bot_login_start(self, redirect, link):
        ICP = request.env['ir.config_parameter'].sudo()
        bot_username = ICP.get_param('auth_telegram.bot_username')
        Login = request.env['auth.telegram.login'].sudo()
        link_uid = request.session.uid if link else False
        # reuse the request this browser already started (page reload, coming
        # back from Telegram) so a confirmation already given is not lost
        login = Login._get_by_token(request.session.get(SESSION_LOGIN_KEY), states=('pending', 'confirmed'))
        if not login or (login.link_user_id.id or False) != (link_uid or False):
            httprequest = request.httprequest
            login = Login._create_request(
                redirect=redirect, link_uid=link_uid,
                requester_ip=httprequest.remote_addr,
                requester_device=_device_label(httprequest.user_agent.string))
            # the token only ever lives in this browser's session and in the
            # Telegram deep link: never in a URL the browser requests
            request.session[SESSION_LOGIN_KEY] = login.token
        elif redirect and login.redirect != redirect:
            login.redirect = redirect

        deeplink = 'https://t.me/%s?start=%s' % (bot_username, login.token)
        qr_src = False
        try:
            png = request.env['ir.actions.report'].sudo().barcode('QR', deeplink, width=180, height=180)
            qr_src = 'data:image/png;base64,' + base64.b64encode(png).decode()
        except Exception:  # noqa: BLE001 - the QR code is a convenience only
            _logger.debug("Telegram login: could not render the QR code", exc_info=True)

        params = {}
        if link:
            params['link'] = '1'
        if redirect:
            params['redirect'] = redirect
        retry_url = '/auth/telegram/login' + ('?%s' % urlencode(params) if params else '')
        user = request.env.user if request.session.uid else None
        return request.render('auth_telegram.bot_login_page', {
            'deeplink': deeplink,
            'qr_src': qr_src,
            'bot_username': bot_username,
            'is_link': bool(link),
            'match_code': login.code if ICP.get_param('auth_telegram.bot_match_code') == '1' else False,
            'retry_url': retry_url,
            'home_url': ('/odoo' if user._is_internal() else '/my') if user else '/web/login',
            'disable_database_manager': True,
            'disable_footer': True,
        })

    @http.route('/auth/telegram/status', type='http', auth='public', methods=['GET'], save_session=False)
    def telegram_status(self, **kw):
        """ Polled by the login page while the user confirms in Telegram. The
            request is identified by the browser session, not by a URL parameter. """
        login = request.env['auth.telegram.login'].sudo()._get_by_token(request.session.get(SESSION_LOGIN_KEY))
        response = request.make_json_response({'state': login.state if login else 'invalid'})
        response.headers['Cache-Control'] = 'no-store'
        return response

    @http.route('/auth/telegram/complete', type='http', auth='none', methods=['GET'], readonly=False)
    def telegram_complete(self, **kw):
        """ Final step of the chat flow, reached by the page that started the
            request once Telegram confirmed it. Only the browser session that
            created the request can complete it, and only once. """
        ensure_db()
        token = request.session.get(SESSION_LOGIN_KEY)
        if not token:
            return request.redirect('/web/login?telegram_error=session')
        dbname = request.db
        registry = Registry(dbname)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            login = env['auth.telegram.login']._get_by_token(token)
            if login:
                login._lock()
            if not login or login.state != 'confirmed':
                if login and login.state == 'done':
                    # completed by another tab of the same browser
                    request.session.pop(SESSION_LOGIN_KEY, None)
                    return request.redirect('/web')
                return request.redirect('/web/login?telegram_error=validation')
            login.state = 'done'
            request.session.pop(SESSION_LOGIN_KEY, None)

            if login.link_user_id:
                if request.session.uid != login.link_user_id.id:
                    cr.commit()
                    return request.redirect('/web/login?redirect=%s' % urlquote('/auth/telegram/link?error=session'))
                Bot = env['telegram.bot']
                validation = login._validation()
                validation['picture'], validation['picture_key'] = Bot._profile_photo(login.telegram_uid)
                user = env['res.users']._auth_telegram_link(login.link_user_id.id, validation)
                if not user:
                    cr.commit()
                    return request.redirect('/auth/telegram/link?error=taken')
                Bot._notify_linked(login, user)
                cr.commit()
                return request.redirect('/auth/telegram/link?success=linked')

            user = login.user_id
            if not user or not user.active:
                cr.commit()
                return request.redirect('/web/login?telegram_error=no-account')
            key = user._auth_telegram_issue_token()
            login_name = user.login
            redirect_url = self._telegram_safe_redirect(login.redirect, user)
            cr.commit()
        return self._telegram_authenticate(dbname, login_name, key, redirect_url)

    @http.route('/auth/telegram/webhook', type='http', auth='public', methods=['POST'],
                csrf=False, save_session=False)
    def telegram_webhook(self, **kw):
        """ Telegram Bot API webhook (messages and button callbacks). """
        secret = request.env['ir.config_parameter'].sudo().get_param('auth_telegram.webhook_secret') or ''
        provided = request.httprequest.headers.get('X-Telegram-Bot-Api-Secret-Token') or ''
        if not secret or not secrets.compare_digest(secret.encode(), provided.encode('utf-8', 'replace')):
            return request.make_json_response({'ok': False, 'error': 'forbidden'}, status=403)
        try:
            update = request.get_json_data()
        except Exception:  # noqa: BLE001
            return request.make_json_response({'ok': False, 'error': 'bad json'}, status=400)
        try:
            with request.env.cr.savepoint():
                request.env['telegram.bot'].sudo()._handle_update(update)
        except Exception:  # noqa: BLE001
            # the handler's database changes were rolled back: drop the
            # Telegram messages it queued for after commit as well. Always
            # acknowledge, otherwise Telegram keeps re-sending the update.
            request.env.cr.postcommit.clear()
            _logger.exception("Telegram webhook: error while handling update %s",
                              update.get('update_id') if isinstance(update, dict) else None)
        return request.make_json_response({'ok': True})

    # ------------------------------------------------------------------
    # OpenID Connect callback (and legacy widget)
    # ------------------------------------------------------------------

    @http.route('/auth/telegram/callback', type='http', auth='none', methods=['GET'], readonly=False)
    def telegram_callback(self, **kw):
        """ Redirect target of both the OIDC flow (?code=...&state=...) and
            the legacy Login Widget (?id=...&hash=...). """
        ensure_db()
        if kw.get('code') or kw.get('error'):
            return self._telegram_oidc_callback(kw)
        if kw.get('link_nonce'):
            return self._telegram_widget_link_callback(kw)
        return self._telegram_widget_callback(kw)

    def _telegram_oidc_callback(self, kw):
        flow = request.session.pop('telegram_oauth', None) or {}
        link_uid = flow.get('link_uid')
        if kw.get('error'):
            # e.g. the user cancelled on the Telegram consent screen
            _logger.info("Telegram OIDC: authorization error: %s", kw['error'])
            if link_uid:
                return request.redirect('/auth/telegram/link?error=failed')
            return request.redirect('/web/login?telegram_error=failed')
        state = kw.get('state') or ''
        if not flow.get('state') or not secrets.compare_digest(flow['state'], state):
            return request.redirect('/web/login?telegram_error=validation')

        dbname = request.db
        if link_uid and link_uid != request.session.uid:
            return request.redirect('/web/login?telegram_error=validation')
        registry = Registry(dbname)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            Users = env['res.users']
            try:
                validation = Users._auth_telegram_oidc_validate(
                    kw.get('code'), flow.get('verifier'), _telegram_callback_uri(), flow.get('nonce'))
            except AccessDenied:
                _logger.info("Telegram OIDC: validation failed (remote %s)",
                             request.httprequest.remote_addr)
                if link_uid:
                    return request.redirect('/auth/telegram/link?error=validation')
                return request.redirect('/web/login?telegram_error=validation')
            if link_uid:
                if not Users._auth_telegram_link(link_uid, validation):
                    return request.redirect('/auth/telegram/link?error=taken')
                cr.commit()
                return request.redirect('/auth/telegram/link?success=linked')
            try:
                user, key = Users._auth_telegram_signin(validation)
            except AccessDenied:
                _logger.info("Telegram login: no user for Telegram uid %s and sign up refused",
                             validation.get('id'))
                return request.redirect('/web/login?telegram_error=no-account')
            login = user.login
            redirect_url = self._telegram_safe_redirect(flow.get('redirect'), user)
            cr.commit()
        return self._telegram_authenticate(dbname, login, key, redirect_url)

    # ------------------------------------------------------------------
    # legacy Login Widget flow
    # ------------------------------------------------------------------

    def _telegram_widget_callback(self, kw):
        dbname = request.db
        registry = Registry(dbname)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            Users = env['res.users']
            if not Users._auth_telegram_enabled():
                return request.redirect('/web/login?telegram_error=failed')
            try:
                validation = Users._auth_telegram_validate(dict(kw))
            except AccessDenied:
                _logger.info("Telegram login: payload verification failed (remote %s)",
                             request.httprequest.remote_addr)
                return request.redirect('/web/login?telegram_error=validation')
            try:
                user, key = Users._auth_telegram_signin(validation)
            except AccessDenied:
                _logger.info("Telegram login: no user for Telegram uid %s and sign up refused",
                             validation.get('id'))
                return request.redirect('/web/login?telegram_error=no-account')
            login = user.login
            redirect_url = self._telegram_safe_redirect(kw.get('redirect'), user)
            cr.commit()
        return self._telegram_authenticate(dbname, login, key, redirect_url)

    def _telegram_widget_link_callback(self, kw):
        expected_nonce = request.session.pop('telegram_link_nonce', None)
        uid = request.session.uid
        if not (uid and expected_nonce and secrets.compare_digest(expected_nonce, kw['link_nonce'])):
            return request.redirect('/web/login?telegram_error=validation')
        registry = Registry(request.db)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            Users = env['res.users']
            try:
                validation = Users._auth_telegram_validate(dict(kw))
            except AccessDenied:
                return request.redirect('/auth/telegram/link?error=validation')
            if not Users._auth_telegram_link(uid, validation):
                return request.redirect('/auth/telegram/link?error=taken')
            cr.commit()
        return request.redirect('/auth/telegram/link?success=linked')

    # ------------------------------------------------------------------
    # account linking page
    # ------------------------------------------------------------------

    @http.route('/auth/telegram/link', type='http', auth='user', methods=['GET'],
                website=True, multilang=False, sitemap=False)
    def telegram_link(self, **kw):
        """ Page from which a logged-in user can link / unlink their own
            Telegram account. Users who have a password must confirm it first
            (adding a way to sign in is a credential change). """
        mode = request.env['res.users'].sudo()._auth_telegram_mode()
        if not mode:
            return request.redirect('/web/login')
        user = request.env.user
        identity_checked = self._telegram_identity_checked()
        values = {
            'user_name': user.name,
            'telegram_username': user.sudo().telegram_username,
            'telegram_uid': user.sudo().telegram_uid,
            'home_url': '/odoo' if user._is_internal() else '/my',
            'link_error': kw.get('error'),
            'link_success': kw.get('success'),
            'needs_password': not identity_checked,
            'can_unlink': self._telegram_can_recover(user),
            'disable_database_manager': True,
            'disable_footer': True,
        }
        if identity_checked:
            if mode in ('bot', 'oidc'):
                values['telegram_login_url'] = '/auth/telegram/login?link=1'
            else:
                nonce = secrets.token_urlsafe(24)
                request.session['telegram_link_nonce'] = nonce
                auth_url = '%s?%s' % (_telegram_callback_uri(), urlencode({'link_nonce': nonce}))
                values.update({
                    'telegram_bot_username': request.env['ir.config_parameter'].sudo().get_param('auth_telegram.bot_username'),
                    'telegram_auth_url': auth_url,
                })
        return request.render('auth_telegram.link_account_page', values)

    @http.route('/auth/telegram/link/verify', type='http', auth='user', methods=['POST'])
    def telegram_link_verify(self, password=None, **kw):
        """ Password re-check before linking / unlinking (same session flag
            as Odoo's check_identity, valid 10 minutes). """
        try:
            if not password:
                raise AccessDenied()
            request.env.user._check_credentials(
                {'type': 'password', 'password': password}, {'interactive': True})
        except AccessDenied:
            return request.redirect('/auth/telegram/link?error=password')
        request.session['identity-check-last'] = time.time()
        return request.redirect('/auth/telegram/link')

    @http.route('/auth/telegram/unlink', type='http', auth='user', methods=['POST'])
    def telegram_unlink(self, **kw):
        user = request.env.user
        if not self._telegram_identity_checked():
            return request.redirect('/auth/telegram/link?error=password')
        if not self._telegram_can_recover(user):
            # Telegram is the only way into this account: unlinking it would
            # lock the user out for good
            return request.redirect('/auth/telegram/link?error=no-fallback')
        user.sudo()._auth_telegram_unlink()
        return request.redirect('/auth/telegram/link?success=unlinked')

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _telegram_has_password(self, user):
        request.env.cr.execute("SELECT COALESCE(password, '') != '' FROM res_users WHERE id = %s", [user.id])
        row = request.env.cr.fetchone()
        return bool(row and row[0])

    def _telegram_can_recover(self, user):
        """ Can the user still sign in / reset a password without Telegram?
            (accounts created by the Telegram sign up have neither a password
            nor a real email address) """
        return self._telegram_has_password(user) or bool(email_normalize(user.email or ''))

    def _telegram_identity_checked(self):
        """ Users with a password must have re-entered it recently before
            changing their Telegram link; accounts without a password have
            nothing else to re-check. """
        if not self._telegram_has_password(request.env.user):
            return True
        last = request.session.get('identity-check-last') or 0
        return time.time() - last < IDENTITY_CHECK_VALIDITY

    def _telegram_authenticate(self, dbname, login, key, redirect_url):
        credential = {'login': login, 'token': key, 'type': 'telegram_token'}
        try:
            # same flow as the standard login: authenticate on the current
            # session, the http layer rotates it and sets the cookie
            auth_info = request.session.authenticate(dbname, credential)
        except AccessDenied:
            return request.redirect('/web/login?telegram_error=failed')
        uid = auth_info['uid'] if isinstance(auth_info, dict) else auth_info
        # users with 2FA only get a partial session here and must go through
        # /web/login/totp first, like after the standard login form
        return request.redirect(self._telegram_post_login_url(uid, redirect_url))

    def _telegram_post_login_url(self, uid, redirect_url):
        if _get_login_redirect_url is not None:
            return _get_login_redirect_url(uid, redirect_url)
        if request.session.uid:
            return redirect_url
        mfa_url = request.env['res.users'].sudo().browse(uid)._mfa_url() or '/web/login'
        return '%s%s%s' % (mfa_url, '&' if '?' in mfa_url else '?', urlencode({'redirect': redirect_url}))

    def _telegram_safe_redirect(self, redirect, user):
        # only same-origin path redirects; anything else falls back to home
        if redirect and redirect.startswith('/') and not redirect.startswith('//') and '\\' not in redirect:
            return redirect
        return '/odoo' if user._is_internal() else '/my'
