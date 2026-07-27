# -*- coding: utf-8 -*-
import logging
import time

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class ChatflowFlow(models.Model):
    _name = 'chatflow.flow'
    _description = 'ChatFlow Flow'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    step_ids = fields.One2many(
        'chatflow.flow.step', 'flow_id', string='Steps', copy=True)
    trigger_ids = fields.One2many(
        'chatflow.trigger', 'flow_id', string='Triggers')
    times_triggered = fields.Integer(readonly=True, copy=False)
    step_count = fields.Integer(compute='_compute_step_count')

    def _compute_step_count(self):
        for flow in self:
            flow.step_count = len(flow.step_ids)

    def run(self, subscriber, messaging_type='RESPONSE', tag=None):
        """Execute every step of the flow for one subscriber.

        Returns True when all message steps were accepted by the Send API.
        """
        self.ensure_one()
        success = True
        for step in self.step_ids.sorted(key=lambda s: (s.sequence, s.id)):
            try:
                ok = step._execute(
                    subscriber, messaging_type=messaging_type, tag=tag)
                success = success and ok is not False
            except Exception:
                _logger.exception(
                    "chatflow: step %s of flow '%s' failed for subscriber %s",
                    step.id, self.name, subscriber.id)
                success = False
        self.sudo().times_triggered += 1
        return success

    def _first_text(self):
        """First textual content of the flow (used for comment replies)."""
        self.ensure_one()
        for step in self.step_ids.sorted(key=lambda s: (s.sequence, s.id)):
            if step.step_type in ('text', 'voice', 'quick_replies', 'buttons') \
                    and step.message:
                return step.message
        return False


class ChatflowFlowStep(models.Model):
    _name = 'chatflow.flow.step'
    _description = 'ChatFlow Flow Step'
    _order = 'sequence, id'

    flow_id = fields.Many2one(
        'chatflow.flow', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    step_type = fields.Selection([
        ('text', 'Text Message'),
        ('voice', 'Voice Message (Text-to-Speech)'),
        ('image', 'Image'),
        ('quick_replies', 'Text + Quick Replies'),
        ('buttons', 'Text + Buttons'),
        ('typing', 'Typing Indicator / Pause'),
        ('add_tag', 'Action: Add Tag'),
        ('remove_tag', 'Action: Remove Tag'),
        ('create_lead', 'Action: Create CRM Lead'),
        ('handoff', 'Action: Human Handoff'),
    ], required=True, default='text')
    message = fields.Text(
        translate=True,
        help="Message text. For voice steps this text is converted to "
             "speech in the page's voice language.")
    image_url = fields.Char(
        help="Public HTTPS URL of the image to send.")
    button_ids = fields.One2many(
        'chatflow.flow.step.button', 'step_id', string='Buttons', copy=True)
    tag_id = fields.Many2one(
        'chatflow.tag', string='Tag',
        help="Tag added to / removed from the subscriber.")
    delay = fields.Integer(
        string='Pause (seconds)', default=2,
        help="Duration of the typing indicator pause (max 10 seconds).")

    def _execute(self, subscriber, messaging_type='RESPONSE', tag=None):
        self.ensure_one()
        page = subscriber.page_id.sudo()
        send_kwargs = {'messaging_type': messaging_type, 'tag': tag}
        step_type = self.step_type

        if step_type == 'text':
            return page._send_message(
                subscriber, {'text': self.message}, self.message,
                message_type='text', **send_kwargs)

        if step_type == 'voice':
            attachment_id = page._get_voice_attachment(self.message)
            if attachment_id:
                return page._send_message(
                    subscriber,
                    {'attachment': {
                        'type': 'audio',
                        'payload': {'attachment_id': attachment_id},
                    }},
                    self.message, message_type='audio', **send_kwargs)
            # TTS unavailable: degrade gracefully to a text message.
            return page._send_message(
                subscriber, {'text': self.message}, self.message,
                message_type='text', **send_kwargs)

        if step_type == 'image':
            return page._send_message(
                subscriber,
                {'attachment': {
                    'type': 'image',
                    'payload': {'url': self.image_url, 'is_reusable': True},
                }},
                self.image_url, message_type='image', **send_kwargs)

        if step_type == 'quick_replies':
            quick_replies = [{
                'content_type': 'text',
                'title': button.name[:20],
                'payload': button._payload(),
            } for button in self.button_ids]
            return page._send_message(
                subscriber,
                {'text': self.message, 'quick_replies': quick_replies},
                self.message, message_type='text', **send_kwargs)

        if step_type == 'buttons':
            buttons = [button._button_template()
                       for button in self.button_ids[:3]]
            return page._send_message(
                subscriber,
                {'attachment': {
                    'type': 'template',
                    'payload': {
                        'template_type': 'button',
                        'text': self.message,
                        'buttons': buttons,
                    },
                }},
                self.message, message_type='text', **send_kwargs)

        if step_type == 'typing':
            page._send_sender_action(subscriber.psid, 'typing_on')
            time.sleep(min(max(self.delay, 0), 10))
            return True

        if step_type == 'add_tag':
            if self.tag_id:
                subscriber.sudo().tag_ids = [(4, self.tag_id.id)]
            return True

        if step_type == 'remove_tag':
            if self.tag_id:
                subscriber.sudo().tag_ids = [(3, self.tag_id.id)]
            return True

        if step_type == 'create_lead':
            return self._create_lead(subscriber)

        if step_type == 'handoff':
            subscriber._handoff(note=self.message)
            return True

        return True

    def _create_lead(self, subscriber):
        if 'crm.lead' not in self.env:
            _logger.warning(
                "chatflow: 'Create CRM Lead' step skipped, the CRM app "
                "is not installed.")
            return True
        last_messages = self.env['chatflow.message'].sudo().search(
            [('subscriber_id', '=', subscriber.id), ('direction', '=', 'in')],
            limit=5)
        description = '\n'.join(
            message.body or '' for message in reversed(last_messages))
        self.env['crm.lead'].sudo().create({
            'name': _('Messenger: %s', subscriber.name),
            'contact_name': subscriber.name,
            'partner_id': subscriber.partner_id.id or False,
            'description': description,
            'referred': 'ChatFlow (%s)' % subscriber.page_id.name,
        })
        subscriber.message_post(body=_("CRM lead created by flow."))
        return True


class ChatflowFlowStepButton(models.Model):
    _name = 'chatflow.flow.step.button'
    _description = 'ChatFlow Step Button / Quick Reply'
    _order = 'sequence, id'

    step_id = fields.Many2one(
        'chatflow.flow.step', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Label', required=True, translate=True)
    button_type = fields.Selection([
        ('flow', 'Start a Flow'),
        ('url', 'Open a Website'),
    ], required=True, default='flow')
    target_flow_id = fields.Many2one(
        'chatflow.flow', string='Flow to Start', ondelete='set null')
    url = fields.Char(string='Website URL')

    def _payload(self):
        self.ensure_one()
        if self.button_type == 'flow' and self.target_flow_id:
            return 'CHATFLOW_FLOW_%d' % self.target_flow_id.id
        return 'CHATFLOW_NOOP'

    def _button_template(self):
        self.ensure_one()
        if self.button_type == 'url':
            return {
                'type': 'web_url',
                'title': self.name[:20],
                'url': self.url or '',
            }
        return {
            'type': 'postback',
            'title': self.name[:20],
            'payload': self._payload(),
        }
