# Part of the auth_telegram module. License LGPL-3.
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


class TelegramAuthHome(Home):

    @http.route()
    def web_login(self, *args, **kw):
        response = super().web_login(*args, **kw)
        if getattr(response, 'is_qweb', False):
            response.qcontext.update(self._auth_telegram_login_qcontext())
        return response

    def _auth_telegram_login_qcontext(self):
        values = {}
        if request.env['res.users'].sudo()._auth_telegram_enabled():
            bot_username = request.env['ir.config_parameter'].sudo().get_param('auth_telegram.bot_username')
            auth_url = urljoin(request.httprequest.url_root, '/auth/telegram/callback')
            redirect = request.params.get('redirect')
            if redirect:
                auth_url = '%s?%s' % (auth_url, urlencode({'redirect': redirect}))
            values.update(telegram_bot_username=bot_username, telegram_auth_url=auth_url)
        error_code = request.params.get('telegram_error')
        if error_code:
            values['error'] = _telegram_error_message(error_code)
        return values


class TelegramAuthController(http.Controller):

    @http.route('/auth/telegram/callback', type='http', auth='none', methods=['GET'])
    def telegram_callback(self, **kw):
        """ Redirect target of the Telegram Login Widget, for both the login
            flow (login page button) and the account linking flow. """
        ensure_db()
        if kw.get('link_nonce'):
            return self._telegram_link_callback(kw)

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

        credential = {'login': login, 'token': key, 'type': 'telegram_token'}
        try:
            # same flow as the standard login: authenticate on the current
            # session, the http layer rotates it and sets the cookie
            request.session.authenticate(dbname, credential)
        except AccessDenied:
            return request.redirect('/web/login?telegram_error=failed')
        return request.redirect(redirect_url)

    @http.route('/auth/telegram/link', type='http', auth='user', methods=['GET'])
    def telegram_link(self, **kw):
        """ Page from which a logged-in user can link / unlink their own
            Telegram account. The widget round-trips a nonce bound to the
            session so that a forged callback cannot link someone else's
            Telegram account (login CSRF). """
        if not request.env['res.users'].sudo()._auth_telegram_enabled():
            return request.redirect('/web/login')
        nonce = secrets.token_urlsafe(24)
        request.session['telegram_link_nonce'] = nonce
        auth_url = urljoin(request.httprequest.url_root, '/auth/telegram/callback')
        auth_url = '%s?%s' % (auth_url, urlencode({'link_nonce': nonce}))
        user = request.env.user
        return request.render('auth_telegram.link_account_page', {
            'telegram_bot_username': request.env['ir.config_parameter'].sudo().get_param('auth_telegram.bot_username'),
            'telegram_auth_url': auth_url,
            'user_name': user.name,
            'telegram_username': user.sudo().telegram_username,
            'telegram_uid': user.sudo().telegram_uid,
            'home_url': '/odoo' if user._is_internal() else '/my',
            'link_error': kw.get('error'),
            'link_success': kw.get('success'),
            'disable_database_manager': True,
            'disable_footer': True,
        })

    @http.route('/auth/telegram/unlink', type='http', auth='user', methods=['POST'])
    def telegram_unlink(self, **kw):
        request.env.user.sudo().write({'telegram_uid': False, 'telegram_username': False})
        return request.redirect('/auth/telegram/link?success=unlinked')

    def _telegram_link_callback(self, kw):
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

    def _telegram_safe_redirect(self, redirect, user):
        # only same-origin path redirects; anything else falls back to home
        if redirect and redirect.startswith('/') and not redirect.startswith('//') and '\\' not in redirect:
            return redirect
        return '/odoo' if user._is_internal() else '/my'
