# -*- coding: utf-8 -*-
import hashlib
import hmac
import io
import json
import logging
import secrets

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from gtts import gTTS
except ImportError:
    gTTS = None
    _logger.info("chatflow: python package 'gtts' is not installed, "
                 "voice (TTS) replies are disabled.")


class ChatflowPage(models.Model):
    _name = 'chatflow.page'
    _description = 'ChatFlow Facebook Page'
    _inherit = ['mail.thread']

    name = fields.Char(required=True, tracking=True)
    page_fb_id = fields.Char(
        string='Facebook Page ID', tracking=True,
        help="Numeric ID of the Facebook Page. Used to match incoming "
             "webhook events when several pages are connected.")
    page_access_token = fields.Char(
        string='Page Access Token', groups='chatflow.group_chatflow_manager',
        help="Token from Meta app > Messenger > Access Tokens.")
    verify_token = fields.Char(
        string='Webhook Verify Token', groups='chatflow.group_chatflow_manager',
        default=lambda self: secrets.token_urlsafe(16),
        help="Secret string used once when registering the webhook "
             "callback URL in the Meta app dashboard.")
    app_secret = fields.Char(
        string='App Secret', groups='chatflow.group_chatflow_manager',
        help="Meta app secret, used to check webhook signatures. "
             "Leave empty to skip signature validation.")
    graph_api_version = fields.Char(default='v21.0', required=True)
    tts_lang = fields.Char(
        string='Voice Language', default='km', required=True,
        help="Language code used for text-to-speech voice replies "
             "(km = Khmer).")
    reply_to_comments = fields.Boolean(
        string='Auto-Reply to Post Comments', default=True)
    handoff_user_id = fields.Many2one(
        'res.users', string='Handoff Responsible',
        help="User notified when a conversation is handed off to a human.")
    active = fields.Boolean(default=True)
    webhook_url = fields.Char(compute='_compute_webhook_url')
    subscriber_count = fields.Integer(compute='_compute_subscriber_count')

    _sql_constraints = [
        ('page_fb_id_uniq', 'unique(page_fb_id)',
         'This Facebook Page is already connected.'),
    ]

    def _compute_webhook_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for page in self:
            page.webhook_url = '%s/chatflow/webhook' % base_url

    def _compute_subscriber_count(self):
        counts = dict(self.env['chatflow.subscriber']._read_group(
            [('page_id', 'in', self.ids)], ['page_id'], ['__count']))
        for page in self:
            page.subscriber_count = counts.get(page, 0)

    def action_view_subscribers(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'chatflow.action_chatflow_subscriber')
        action['domain'] = [('page_id', '=', self.id)]
        action['context'] = {'default_page_id': self.id}
        return action

    # ------------------------------------------------------------------
    # Graph API helpers
    # ------------------------------------------------------------------
    def _graph_url(self, path):
        self.ensure_one()
        return 'https://graph.facebook.com/%s/%s' % (self.graph_api_version, path)

    def _graph_post(self, path, timeout=30, **kwargs):
        """POST to the Graph API. Returns (ok, json_or_error_text)."""
        page = self.sudo()
        if not page.page_access_token:
            return False, "Page '%s' has no access token configured." % page.name
        params = kwargs.pop('params', {})
        params['access_token'] = page.page_access_token
        try:
            response = requests.post(
                page._graph_url(path), params=params, timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            _logger.error("chatflow: Graph API request failed: %s", exc)
            return False, str(exc)
        if not response.ok:
            _logger.error("chatflow: Graph API error %s: %s",
                          response.status_code, response.text)
            return False, response.text
        return True, response.json()

    def _send_api(self, psid, message, messaging_type='RESPONSE', tag=None):
        """Send a message dict through the Messenger Send API."""
        self.ensure_one()
        payload = {
            'recipient': {'id': psid},
            'messaging_type': messaging_type,
            'message': message,
        }
        if tag:
            payload['tag'] = tag
        return self._graph_post('me/messages', json=payload)

    def _send_sender_action(self, psid, action='typing_on'):
        self.ensure_one()
        return self._graph_post(
            'me/messages',
            json={'recipient': {'id': psid}, 'sender_action': action})

    def _send_message(self, subscriber, message, body, message_type='text',
                      messaging_type='RESPONSE', tag=None, is_bot=True):
        """Send through the Send API and log a chatflow.message. Returns bool."""
        self.ensure_one()
        ok, result = self._send_api(
            subscriber.psid, message, messaging_type=messaging_type, tag=tag)
        self.env['chatflow.message'].sudo().create({
            'page_id': self.id,
            'subscriber_id': subscriber.id,
            'direction': 'out',
            'body': body,
            'message_type': message_type,
            'is_bot': is_bot,
            'error': False if ok else str(result)[:500],
        })
        return ok

    def _reply_to_comment(self, comment_id, text):
        """Reply to a comment on a Page post."""
        self.ensure_one()
        ok, result = self._graph_post(
            '%s/comments' % comment_id, json={'message': text})
        self.env['chatflow.message'].sudo().create({
            'page_id': self.id,
            'direction': 'out',
            'body': text,
            'message_type': 'comment',
            'is_bot': True,
            'error': False if ok else str(result)[:500],
        })
        return ok

    # ------------------------------------------------------------------
    # Voice (text-to-speech) attachments
    # ------------------------------------------------------------------
    def _get_voice_attachment(self, text):
        """Return a reusable Facebook attachment id for the spoken `text`.

        The MP3 is synthesized once per (language, text) pair, uploaded to
        Facebook once, and the reusable attachment id is cached.
        Returns None when TTS is unavailable or the upload failed.
        """
        self.ensure_one()
        page = self.sudo()
        if gTTS is None:
            _logger.warning(
                "chatflow: voice step skipped, install the 'gtts' python "
                "package on the Odoo server to enable TTS replies.")
            return None
        digest = hashlib.sha1(
            ('%s:%s' % (page.tts_lang, text)).encode('utf-8')).hexdigest()
        Cache = self.env['chatflow.attachment.cache'].sudo()
        cached = Cache.search([
            ('page_id', '=', page.id), ('digest', '=', digest)], limit=1)
        if cached:
            return cached.attachment_fb_id
        try:
            buffer = io.BytesIO()
            gTTS(text=text, lang=page.tts_lang).write_to_fp(buffer)
            buffer.seek(0)
        except Exception as exc:
            _logger.error("chatflow: TTS synthesis failed: %s", exc)
            return None
        ok, result = page._graph_post(
            'me/message_attachments',
            timeout=60,
            data={'message': json.dumps({
                'attachment': {
                    'type': 'audio',
                    'payload': {'is_reusable': True},
                },
            })},
            files={'filedata': ('%s.mp3' % digest, buffer, 'audio/mpeg')})
        if not ok:
            return None
        attachment_id = result.get('attachment_id')
        if attachment_id:
            Cache.create({
                'page_id': page.id,
                'digest': digest,
                'attachment_fb_id': attachment_id,
            })
        return attachment_id

    # ------------------------------------------------------------------
    # Webhook helpers
    # ------------------------------------------------------------------
    @api.model
    def _verify_webhook_signature(self, raw_body, signature_header):
        """Validate X-Hub-Signature-256 against connected pages' app secrets.

        Pages without an app secret configured do not enforce validation
        (same behaviour as leaving APP_SECRET empty in a standalone bot).
        """
        pages = self.sudo().search([])
        app_secrets = {p.app_secret for p in pages if p.app_secret}
        if not app_secrets:
            return True
        if not signature_header.startswith('sha256='):
            return False
        received = signature_header[len('sha256='):]
        for secret in app_secrets:
            expected = hmac.new(
                secret.encode(), raw_body, hashlib.sha256).hexdigest()
            if hmac.compare_digest(received, expected):
                return True
        return False

    @api.model
    def _find_for_entry(self, entry_page_id):
        """Map a webhook entry id to a connected page."""
        page = self.sudo().search(
            [('page_fb_id', '=', str(entry_page_id))], limit=1)
        if not page:
            pages = self.sudo().search([])
            if len(pages) == 1:
                page = pages
        return page

    def action_setup_get_started(self):
        """Configure the Messenger 'Get Started' button on the page so the
        Welcome trigger fires for new conversations."""
        self.ensure_one()
        ok, result = self._graph_post('me/messenger_profile', json={
            'get_started': {'payload': 'CHATFLOW_GET_STARTED'},
        })
        if not ok:
            raise UserError(
                _("Could not configure the Get Started button:\n%s", result))
        self.message_post(body=_("Messenger 'Get Started' button configured."))
        return True


class ChatflowAttachmentCache(models.Model):
    _name = 'chatflow.attachment.cache'
    _description = 'ChatFlow Reusable Attachment Cache'

    page_id = fields.Many2one(
        'chatflow.page', required=True, ondelete='cascade', index=True)
    digest = fields.Char(required=True, index=True)
    attachment_fb_id = fields.Char(
        string='Facebook Attachment ID', required=True)

    _sql_constraints = [
        ('page_digest_uniq', 'unique(page_id, digest)',
         'Attachment already cached for this page.'),
    ]
