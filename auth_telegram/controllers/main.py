# Part of the auth_telegram module. License LGPL-3.
import base64
import hashlib
import logging
import secrets
from urllib.parse import urlencode, urljoin

from odoo import api, http, SUPERUSER_ID, _
from odoo.exceptions import AccessDenied
from odoo.http import request
from odoo.modules.registry import Registry
from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.utils import ensure_db

_logger = logging.getLogger(__name__)


def _telegram_error_message(code):
    return {
        'validation': _("Your Telegram sign in could not be verified. Please try again."),
        'no-account': _("No account is linked to this Telegram account, and sign up is not allowed."),
    }.get(code, _("Telegram sign in failed. Please try again."))


def _telegram_callback_uri():
    return urljoin(request.httprequest.url_root, '/auth/telegram/callback')


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
        if mode == 'oidc':
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
    # OpenID Connect flow
    # ------------------------------------------------------------------

    @http.route('/auth/telegram/login', type='http', auth='public', methods=['GET'])
    def telegram_login_start(self, redirect=None, link=None, **kw):
        """ Start the OpenID Connect authorization code flow (with PKCE).
            With `link`, the flow links the Telegram account to the already
            logged-in user instead of signing in. """
        Users = request.env['res.users'].sudo()
        if Users._auth_telegram_mode() != 'oidc':
            return request.redirect('/web/login')
        if link and not request.session.uid:
            return request.redirect('/web/login')
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

    @http.route('/auth/telegram/callback', type='http', auth='none', methods=['GET'])
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
        if kw.get('error'):
            # e.g. the user cancelled on the Telegram consent screen
            _logger.info("Telegram OIDC: authorization error: %s", kw['error'])
            return request.redirect('/web/login?telegram_error=failed')
        state = kw.get('state') or ''
        if not flow.get('state') or not secrets.compare_digest(flow['state'], state):
            return request.redirect('/web/login?telegram_error=validation')

        dbname = request.db
        link_uid = flow.get('link_uid')
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

    @http.route('/auth/telegram/link', type='http', auth='user', methods=['GET'])
    def telegram_link(self, **kw):
        """ Page from which a logged-in user can link / unlink their own
            Telegram account. """
        mode = request.env['res.users'].sudo()._auth_telegram_mode()
        if not mode:
            return request.redirect('/web/login')
        user = request.env.user
        values = {
            'user_name': user.name,
            'telegram_username': user.sudo().telegram_username,
            'telegram_uid': user.sudo().telegram_uid,
            'home_url': '/odoo' if user._is_internal() else '/my',
            'link_error': kw.get('error'),
            'link_success': kw.get('success'),
            'disable_database_manager': True,
            'disable_footer': True,
        }
        if mode == 'oidc':
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

    @http.route('/auth/telegram/unlink', type='http', auth='user', methods=['POST'])
    def telegram_unlink(self, **kw):
        request.env.user.sudo().write({
            'telegram_uid': False,
            'telegram_username': False,
            'telegram_phone': False,
        })
        return request.redirect('/auth/telegram/link?success=unlinked')

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _telegram_authenticate(self, dbname, login, key, redirect_url):
        credential = {'login': login, 'token': key, 'type': 'telegram_token'}
        try:
            # same flow as the standard login: authenticate on the current
            # session, the http layer rotates it and sets the cookie
            request.session.authenticate(dbname, credential)
        except AccessDenied:
            return request.redirect('/web/login?telegram_error=failed')
        return request.redirect(redirect_url)

    def _telegram_safe_redirect(self, redirect, user):
        # only same-origin path redirects; anything else falls back to home
        if redirect and redirect.startswith('/') and not redirect.startswith('//') and '\\' not in redirect:
            return redirect
        return '/odoo' if user._is_internal() else '/my'
