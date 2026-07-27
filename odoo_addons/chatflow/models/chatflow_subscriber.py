# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

import requests

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class ChatflowSubscriber(models.Model):
    _name = 'chatflow.subscriber'
    _description = 'ChatFlow Subscriber'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'last_interaction desc, id desc'

    name = fields.Char(default='Messenger User', required=True, tracking=True)
    psid = fields.Char(
        string='PSID', required=True, index=True,
        help="Page-Scoped ID of this person on Messenger.")
    page_id = fields.Many2one(
        'chatflow.page', string='Page', required=True, ondelete='cascade',
        index=True)
    partner_id = fields.Many2one(
        'res.partner', string='Contact', tracking=True,
        help="Optional link to an Odoo contact.")
    tag_ids = fields.Many2many('chatflow.tag', string='Tags')
    opted_in = fields.Boolean(
        string='Subscribed', default=True, tracking=True,
        help="Unsubscribed people are excluded from broadcasts.")
    bot_paused = fields.Boolean(
        string='Automation Paused', tracking=True,
        help="When paused, the bot stops auto-replying so a human can "
             "take over the conversation. Incoming messages are still "
             "logged.")
    last_interaction = fields.Datetime(
        help="Last time this person messaged the page. Standard Messenger "
             "replies are only allowed within 24 hours of this moment.")
    profile_pic = fields.Char(string='Profile Picture URL')
    chat_message_ids = fields.One2many(
        'chatflow.message', 'subscriber_id', string='Conversation')
    chat_message_count = fields.Integer(compute='_compute_chat_message_count')
    in_24h_window = fields.Boolean(
        compute='_compute_in_24h_window', string='In 24h Window',
        help="True when the last incoming message is less than 24 hours "
             "old, i.e. the page may still send standard messages.")

    _sql_constraints = [
        ('psid_page_uniq', 'unique(psid, page_id)',
         'This subscriber already exists for this page.'),
    ]

    def _compute_chat_message_count(self):
        counts = dict(self.env['chatflow.message']._read_group(
            [('subscriber_id', 'in', self.ids)], ['subscriber_id'], ['__count']))
        for subscriber in self:
            subscriber.chat_message_count = counts.get(subscriber, 0)

    def _compute_in_24h_window(self):
        limit = fields.Datetime.now() - timedelta(hours=24)
        for subscriber in self:
            subscriber.in_24h_window = bool(
                subscriber.last_interaction
                and subscriber.last_interaction >= limit)

    @api.model
    def _find_or_create(self, page, psid):
        subscriber = self.sudo().search([
            ('page_id', '=', page.id), ('psid', '=', psid)], limit=1)
        if not subscriber:
            subscriber = self.sudo().create({
                'page_id': page.id,
                'psid': psid,
            })
            subscriber._fetch_profile()
        return subscriber

    def _fetch_profile(self):
        """Best effort: fetch name and picture from the Graph API."""
        for subscriber in self:
            page = subscriber.page_id.sudo()
            if not page.page_access_token:
                continue
            try:
                response = requests.get(
                    page._graph_url(subscriber.psid),
                    params={
                        'fields': 'first_name,last_name,profile_pic',
                        'access_token': page.page_access_token,
                    },
                    timeout=15)
                if not response.ok:
                    continue
                data = response.json()
                name = ' '.join(filter(None, [
                    data.get('first_name'), data.get('last_name')]))
                values = {}
                if name:
                    values['name'] = name
                if data.get('profile_pic'):
                    values['profile_pic'] = data['profile_pic']
                if values:
                    subscriber.write(values)
            except requests.RequestException as exc:
                _logger.info("chatflow: could not fetch profile of %s: %s",
                             subscriber.psid, exc)

    def action_toggle_pause(self):
        for subscriber in self:
            subscriber.bot_paused = not subscriber.bot_paused

    def action_open_send_message(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Message'),
            'res_model': 'chatflow.send.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_subscriber_id': self.id},
        }

    def action_view_conversation(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'chatflow.action_chatflow_message')
        action['domain'] = [('subscriber_id', '=', self.id)]
        action['context'] = {'default_subscriber_id': self.id,
                             'default_page_id': self.page_id.id}
        return action

    def _handoff(self, note=None):
        """Pause the bot and notify the responsible user."""
        for subscriber in self:
            subscriber.bot_paused = True
            user = (subscriber.page_id.handoff_user_id
                    or self.env.ref('base.user_admin', raise_if_not_found=False))
            body = note or _("Conversation handed off to a human agent.")
            subscriber.message_post(body=body)
            if user:
                subscriber.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('Messenger conversation needs a human reply'),
                    note=body,
                    user_id=user.id)
