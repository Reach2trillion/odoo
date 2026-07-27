# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ChatflowBroadcast(models.Model):
    _name = 'chatflow.broadcast'
    _description = 'ChatFlow Broadcast'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(required=True, tracking=True)
    page_id = fields.Many2one(
        'chatflow.page', string='Page', required=True, ondelete='cascade')
    flow_id = fields.Many2one(
        'chatflow.flow', string='Flow to Send', required=True,
        ondelete='restrict',
        help="The flow executed for every recipient.")
    include_tag_ids = fields.Many2many(
        'chatflow.tag', 'chatflow_broadcast_include_tag_rel',
        string='Recipients With Any Tag',
        help="Only send to subscribers having at least one of these tags. "
             "Leave empty to target all subscribers of the page.")
    exclude_tag_ids = fields.Many2many(
        'chatflow.tag', 'chatflow_broadcast_exclude_tag_rel',
        string='Exclude Tags',
        help="Never send to subscribers having one of these tags.")
    only_recent = fields.Boolean(
        string='Only 24h Window', default=True,
        help="Only send to people who messaged the page in the last "
             "24 hours. Facebook rejects standard messages outside this "
             "window unless a message tag is used.")
    messaging_tag = fields.Selection([
        ('CONFIRMED_EVENT_UPDATE', 'Confirmed Event Update'),
        ('POST_PURCHASE_UPDATE', 'Post-Purchase Update'),
        ('ACCOUNT_UPDATE', 'Account Update'),
    ], help="Facebook message tag allowing delivery outside the 24h "
            "window, only for the non-promotional use cases Facebook "
            "allows for each tag.")
    scheduled_date = fields.Datetime(
        help="Leave empty to send as soon as the broadcast is queued.")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('queued', 'Queued'),
        ('sending', 'Sending'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False)
    line_ids = fields.One2many(
        'chatflow.broadcast.line', 'broadcast_id', string='Recipients',
        copy=False)
    recipient_count = fields.Integer(compute='_compute_counts')
    sent_count = fields.Integer(compute='_compute_counts')
    failed_count = fields.Integer(compute='_compute_counts')

    def _compute_counts(self):
        for broadcast in self:
            lines = broadcast.line_ids
            broadcast.recipient_count = len(lines)
            broadcast.sent_count = len(
                lines.filtered(lambda line: line.state == 'sent'))
            broadcast.failed_count = len(
                lines.filtered(lambda line: line.state == 'failed'))

    def _recipient_domain(self):
        self.ensure_one()
        domain = [
            ('page_id', '=', self.page_id.id),
            ('opted_in', '=', True),
        ]
        if self.include_tag_ids:
            domain.append(('tag_ids', 'in', self.include_tag_ids.ids))
        if self.exclude_tag_ids:
            domain.append(('tag_ids', 'not in', self.exclude_tag_ids.ids))
        if self.only_recent and not self.messaging_tag:
            domain.append(('last_interaction', '>=',
                           fields.Datetime.now() - timedelta(hours=24)))
        return domain

    def action_queue(self):
        for broadcast in self:
            if broadcast.state != 'draft':
                continue
            recipients = self.env['chatflow.subscriber'].search(
                broadcast._recipient_domain())
            if not recipients:
                raise UserError(_(
                    "No recipient matches the audience of broadcast '%s'.",
                    broadcast.name))
            broadcast.line_ids.unlink()
            self.env['chatflow.broadcast.line'].create([{
                'broadcast_id': broadcast.id,
                'subscriber_id': subscriber.id,
            } for subscriber in recipients])
            broadcast.state = 'queued'
        self.env.ref('chatflow.ir_cron_send_broadcasts').sudo()._trigger()
        return True

    def action_cancel(self):
        self.filtered(
            lambda broadcast: broadcast.state in ('queued', 'sending')
        ).state = 'cancelled'
        return True

    def action_reset_to_draft(self):
        for broadcast in self.filtered(
                lambda broadcast: broadcast.state == 'cancelled'):
            broadcast.line_ids.unlink()
            broadcast.state = 'draft'
        return True

    @api.model
    def _cron_send(self, batch_size=50):
        now = fields.Datetime.now()
        broadcasts = self.search(
            [('state', 'in', ('queued', 'sending'))])
        work_left = False
        for broadcast in broadcasts:
            if broadcast.scheduled_date and broadcast.scheduled_date > now:
                work_left = True
                continue
            broadcast.state = 'sending'
            lines = broadcast.line_ids.filtered(
                lambda line: line.state == 'pending')[:batch_size]
            if not lines:
                broadcast.state = 'done'
                broadcast.message_post(body=_(
                    "Broadcast finished: %(sent)s sent, %(failed)s failed.",
                    sent=broadcast.sent_count,
                    failed=broadcast.failed_count))
                continue
            for line in lines:
                line._send()
            work_left = True
            # Persist progress between batches: broadcasts can be large
            # and the Send API is slow.
            self.env.cr.commit()
        if work_left:
            self.env.ref('chatflow.ir_cron_send_broadcasts').sudo()._trigger()


class ChatflowBroadcastLine(models.Model):
    _name = 'chatflow.broadcast.line'
    _description = 'ChatFlow Broadcast Recipient'

    broadcast_id = fields.Many2one(
        'chatflow.broadcast', required=True, ondelete='cascade', index=True)
    subscriber_id = fields.Many2one(
        'chatflow.subscriber', required=True, ondelete='cascade')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ], default='pending', required=True, index=True)
    error = fields.Char()

    def _send(self):
        self.ensure_one()
        broadcast = self.broadcast_id
        messaging_type = ('MESSAGE_TAG' if broadcast.messaging_tag
                          else 'UPDATE')
        try:
            with self.env.cr.savepoint():
                ok = broadcast.flow_id.run(
                    self.subscriber_id,
                    messaging_type=messaging_type,
                    tag=broadcast.messaging_tag or None)
            self.write({
                'state': 'sent' if ok else 'failed',
                'error': False if ok else _(
                    "The Send API rejected at least one message "
                    "(see the conversation log)."),
            })
        except Exception as exc:
            _logger.exception(
                "chatflow: broadcast %s failed for subscriber %s",
                broadcast.id, self.subscriber_id.id)
            self.write({'state': 'failed', 'error': str(exc)[:500]})
