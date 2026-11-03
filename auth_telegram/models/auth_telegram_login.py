# Part of the auth_telegram module. License LGPL-3.
import hashlib
import hmac
import secrets
from datetime import timedelta

from odoo import api, fields, models

# How long (seconds) a login request started on the website stays valid
LOGIN_REQUEST_VALIDITY = 600
# Wrong one-time codes accepted on the website before the request is cancelled
CODE_MAX_ATTEMPTS = 3
# How long (seconds) the "Open website" button of the success message works
OPEN_LINK_VALIDITY = 600


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
    # why the request ended up 'cancelled' (shown on the website page)
    cancel_reason = fields.Selection([
        ('user', 'Cancelled by the user'),
        ('wrong_code', 'Wrong one-time code'),
        ('conflict', 'Opened by another Telegram account'),
        ('no_account', 'No account and sign up refused'),
        ('taken', 'Telegram account linked to another user'),
        ('stale', 'Outdated button'),
    ], readonly=True)
    expiration = fields.Datetime(required=True, readonly=True)
    redirect = fields.Char(readonly=True)
    # One-time code: with "one-time code" enabled (frozen per request in
    # `match_code`), the bot shows `code` in Telegram *after* the user tapped
    # Yes, and the browser that started the request must type it before it can
    # complete the login. The code is never sent to the browser, so somebody
    # who sends a customer their own login link still cannot get in without
    # the customer actively handing the code over.
    match_code = fields.Boolean(readonly=True)
    code = fields.Char(readonly=True)
    code_verified = fields.Boolean(readonly=True)
    code_attempts = fields.Integer(readonly=True, default=0)
    # "Open website" button sent with the success message: a single-use
    # secret (only its hash is stored) that signs in whichever browser opens
    # it, because Telegram opens links in its own browser, which does not
    # share the cookies of the browser where the login was started
    open_token_hash = fields.Char(readonly=True, copy=False, index=True)
    open_token_expiration = fields.Datetime(readonly=True, copy=False)
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
    def _create_request(self, redirect=None, link_uid=False, requester_ip=False,
                        requester_device=False, match_code=False):
        return self.create({
            # [A-Za-z0-9_-], 32 chars: valid as a Telegram /start payload
            'token': secrets.token_urlsafe(24),
            'match_code': bool(match_code),
            'code': '%06d' % secrets.randbelow(10 ** 6),
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
            update, two browser tabs) are serialized.

            Cursors run REPEATABLE READ: when the previous holder of the lock
            changed the row, PostgreSQL raises a serialization failure here
            instead of returning it. The http layer (odoo.service.model
            .retrying) then rolls back and re-runs the whole request on a
            fresh snapshot, which is how the later handler gets to see the
            final state; the expected failure is not logged as a bad query. """
        self.ensure_one()
        self.flush_model()
        self.env.cr.execute('SELECT id FROM auth_telegram_login WHERE id = %s FOR UPDATE',
                            [self.id], log_exceptions=False)
        self.invalidate_recordset()
        return self

    def _cancel(self, reason):
        self.ensure_one()
        self.write({'state': 'cancelled', 'cancel_reason': reason})

    def _needs_code(self):
        """ Confirmed in Telegram, but the one-time code shown there has not
            been typed on the website yet. """
        self.ensure_one()
        return self.state == 'confirmed' and self.match_code and not self.code_verified

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

    def _issue_open_token(self):
        """ New secret for the "Open website" button (replacing any earlier
            one); returns it, only its hash is stored. """
        self.ensure_one()
        key = secrets.token_urlsafe(32)
        self.write({
            'open_token_hash': hashlib.sha256(key.encode()).hexdigest(),
            'open_token_expiration': fields.Datetime.now() + timedelta(seconds=OPEN_LINK_VALIDITY),
        })
        return key

    @api.model
    def _get_by_open_token(self, key):
        """ The request whose "Open website" secret is `key` (empty when
            unknown); see _open_token_usable for whether it may be used. """
        if not key or not isinstance(key, str) or len(key) > 128:
            return self.browse()
        key_hash = hashlib.sha256(key.encode('utf-8', 'replace')).hexdigest()
        return self.search([('open_token_hash', '=', key_hash)], limit=1)

    def _open_token_usable(self, key):
        """ Call after _lock(): `key` is still this request's unused, unexpired
            "Open website" secret, for an approved login of a user that is
            still active and still linked to the Telegram account that
            approved it. """
        self.ensure_one()
        if not (self.open_token_hash and self.open_token_expiration and isinstance(key, str)):
            return False
        if self.open_token_expiration < fields.Datetime.now():
            return False
        if not hmac.compare_digest(self.open_token_hash,
                                   hashlib.sha256(key.encode('utf-8', 'replace')).hexdigest()):
            return False
        # issued on approval: 'expired' only means the browser that started
        # the request did not come back in time, the approval still stands
        if self.link_user_id or self.state not in ('confirmed', 'done', 'expired') or self._needs_code_pending():
            return False
        user = self.user_id
        return bool(user and user.active and self.telegram_uid and user.telegram_uid == self.telegram_uid)

    def _needs_code_pending(self):
        """ One-time code required and not typed yet (whatever the state). """
        self.ensure_one()
        return bool(self.match_code and not self.code_verified)

    def _consume_open_token(self):
        self.ensure_one()
        self.write({'open_token_hash': False, 'open_token_expiration': False})

    @api.autovacuum
    def _gc_login_requests(self):
        self.search([('create_date', '<', fields.Datetime.now() - timedelta(days=1))]).unlink()
