# Part of the auth_telegram module. License LGPL-3.
import secrets
from datetime import timedelta

from odoo import api, fields, models

# How long (seconds) a login request started on the website stays valid
LOGIN_REQUEST_VALIDITY = 600


class AuthTelegramLogin(models.Model):
    """ A "Log in with Telegram" request started from the website, confirmed
        by the user in the bot chat (/start <token> then "Yes, Login") and
        finally completed - once - by the browser that started it. """
    _name = 'auth.telegram.login'
    _description = 'Telegram Login Request'
    _rec_name = 'token'
    _order = 'id desc'

    token = fields.Char(required=True, index=True, copy=False, readonly=True)
    state = fields.Selection([
        ('pending', 'Waiting for Telegram'),
        ('confirmed', 'Confirmed in Telegram'),
        ('done', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ], default='pending', required=True, index=True, readonly=True)
    expiration = fields.Datetime(required=True, readonly=True)
    redirect = fields.Char(readonly=True)
    # two-digit code shown on the website; with "number matching" enabled the
    # user must tap the same number in Telegram instead of a plain "Yes"
    code = fields.Char(readonly=True)
    # where the request was started (shown in the Telegram prompt so the user
    # can spot a request they did not start themselves)
    requester_ip = fields.Char(readonly=True)
    requester_device = fields.Char(readonly=True)
    # set when the request links a Telegram account to an already logged-in user
    link_user_id = fields.Many2one('res.users', ondelete='cascade', readonly=True)
    # resolved Odoo user once confirmed (login flow)
    user_id = fields.Many2one('res.users', ondelete='set null', readonly=True)
    user_created = fields.Boolean(readonly=True)
    telegram_uid = fields.Char(readonly=True)
    telegram_name = fields.Char(readonly=True)
    telegram_username = fields.Char(readonly=True)
    telegram_chat_id = fields.Char(readonly=True)
    telegram_message_id = fields.Char(readonly=True)

    _sql_constraints = [
        ('token_unique', 'unique(token)', 'Login token must be unique.'),
    ]

    @api.model
    def _create_request(self, redirect=None, link_uid=False, requester_ip=False, requester_device=False):
        return self.create({
            # [A-Za-z0-9_-], 32 chars: valid as a Telegram /start payload
            'token': secrets.token_urlsafe(24),
            'code': '%02d' % secrets.randbelow(100),
            'expiration': fields.Datetime.now() + timedelta(seconds=LOGIN_REQUEST_VALIDITY),
            'redirect': redirect or False,
            'link_user_id': link_uid or False,
            'requester_ip': requester_ip or False,
            'requester_device': requester_device or False,
        })

    @api.model
    def _get_by_token(self, token, states=None):
        """ Return the request for `token`, expiring it on the fly when needed;
            an empty recordset when unknown or not in `states`. """
        if not token or not isinstance(token, str) or len(token) > 64:
            return self.browse()
        request = self.search([('token', '=', token)], limit=1)
        if request and request.state in ('pending', 'confirmed') \
                and request.expiration < fields.Datetime.now():
            request.state = 'expired'
        if states and request.state not in states:
            return self.browse()
        return request

    def _lock(self):
        """ Row-lock the request and re-read it, so that concurrent handlers
            of the same request (double tap in Telegram, redelivered webhook
            update, two browser tabs) are serialized and see each other's
            final state. """
        self.ensure_one()
        self.flush_model()
        self.env.cr.execute('SELECT id FROM auth_telegram_login WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset()
        return self

    def _validation(self):
        """ Identity dict in the format expected by res.users._auth_telegram_* """
        self.ensure_one()
        return {
            'id': self.telegram_uid,
            'name': self.telegram_name or False,
            'username': self.telegram_username or False,
            'phone': False,
            'picture': False,
        }

    @api.autovacuum
    def _gc_login_requests(self):
        self.search([('create_date', '<', fields.Datetime.now() - timedelta(days=1))]).unlink()
