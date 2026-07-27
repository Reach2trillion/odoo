# -*- coding: utf-8 -*-
import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ChatflowEvent(models.Model):
    """Queue of raw webhook payloads.

    The webhook controller only stores the payload and returns 200
    immediately (Facebook requires a fast answer); the actual processing
    happens here, from a triggered cron job.
    """
    _name = 'chatflow.event'
    _description = 'ChatFlow Incoming Webhook Event'
    _order = 'id'

    payload = fields.Text(required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ], default='pending', required=True, index=True)
    error = fields.Text()

    @api.model
    def _cron_process(self, limit=100):
        events = self.search([('state', '=', 'pending')], limit=limit)
        for event in events:
            try:
                with self.env.cr.savepoint():
                    event._process()
                event.state = 'done'
            except Exception as exc:
                _logger.exception("chatflow: failed to process event %s",
                                  event.id)
                event.write({'state': 'failed', 'error': str(exc)[:2000]})
        if self.search_count([('state', '=', 'pending')], limit=1):
            self.env.ref('chatflow.ir_cron_process_events').sudo()._trigger()

    def _process(self):
        self.ensure_one()
        payload = json.loads(self.payload)
        Page = self.env['chatflow.page'].sudo()
        for entry in payload.get('entry', []):
            page = Page._find_for_entry(entry.get('id'))
            if not page:
                _logger.warning(
                    "chatflow: no connected page found for webhook entry %s",
                    entry.get('id'))
                continue
            for messaging_event in entry.get('messaging', []):
                self._process_messaging(page, messaging_event)
            for change in entry.get('changes', []):
                if change.get('field') == 'feed':
                    self._process_feed_change(page, change, entry.get('id'))

    # ------------------------------------------------------------------
    # Messenger messages / postbacks
    # ------------------------------------------------------------------
    def _process_messaging(self, page, event):
        message = event.get('message') or {}
        postback = event.get('postback') or {}
        sender_psid = (event.get('sender') or {}).get('id')
        if not sender_psid or message.get('is_echo'):
            return
        if not message and not postback:
            return  # delivery/read receipts, reactions, etc.

        Subscriber = self.env['chatflow.subscriber']
        subscriber = Subscriber._find_or_create(page, sender_psid)
        subscriber.last_interaction = fields.Datetime.now()

        payload_code = ((message.get('quick_reply') or {}).get('payload')
                        or postback.get('payload'))
        text = message.get('text') or postback.get('title') or ''
        message_type = 'postback' if payload_code else 'text'
        if not text and message.get('attachments'):
            attachment_types = {attachment.get('type')
                                for attachment in message['attachments']}
            text = ', '.join(sorted(filter(None, attachment_types)))
            message_type = 'attachment'

        self.env['chatflow.message'].sudo().create({
            'page_id': page.id,
            'subscriber_id': subscriber.id,
            'direction': 'in',
            'body': text or payload_code,
            'message_type': message_type,
        })

        # Button / quick reply clicks always work, even when paused by
        # a keyword conversation handoff.
        if payload_code:
            self._handle_payload(page, subscriber, payload_code)
            return
        if subscriber.bot_paused:
            return
        trigger = self.env['chatflow.trigger']._match_keyword(page, text)
        if trigger:
            trigger._fire(subscriber)

    def _handle_payload(self, page, subscriber, payload_code):
        Trigger = self.env['chatflow.trigger']
        if payload_code in ('CHATFLOW_GET_STARTED', 'GET_STARTED'):
            trigger = Trigger._get_welcome(page)
            if trigger:
                trigger._fire(subscriber)
            return
        if payload_code.startswith('CHATFLOW_FLOW_'):
            try:
                flow_id = int(payload_code[len('CHATFLOW_FLOW_'):])
            except ValueError:
                return
            flow = self.env['chatflow.flow'].sudo().browse(flow_id).exists()
            if flow and flow.active:
                flow.run(subscriber)

    # ------------------------------------------------------------------
    # Comments on Page posts
    # ------------------------------------------------------------------
    def _process_feed_change(self, page, change, entry_id=None):
        if not page.reply_to_comments:
            return
        value = change.get('value') or {}
        if value.get('item') != 'comment' or value.get('verb') != 'add':
            return
        author_id = (value.get('from') or {}).get('id')
        # Never reply to the page's own comments (avoids reply loops).
        if not author_id or author_id in (page.page_fb_id, str(entry_id)):
            return
        comment_id = value.get('comment_id')
        if not comment_id:
            return
        comment_text = value.get('message') or ''
        self.env['chatflow.message'].sudo().create({
            'page_id': page.id,
            'direction': 'in',
            'body': comment_text,
            'message_type': 'comment',
        })
        trigger = self.env['chatflow.trigger']._match_keyword(
            page, comment_text, comments_only=True)
        if not trigger:
            return
        reply = trigger.flow_id._first_text()
        if reply:
            trigger.sudo().hit_count += 1
            page._reply_to_comment(comment_id, reply)
