# -*- coding: utf-8 -*-
from odoo import fields, models


class ChatflowMessage(models.Model):
    _name = 'chatflow.message'
    _description = 'ChatFlow Conversation Message'
    _order = 'create_date desc, id desc'
    _rec_name = 'body'

    page_id = fields.Many2one(
        'chatflow.page', string='Page', required=True, ondelete='cascade',
        index=True)
    subscriber_id = fields.Many2one(
        'chatflow.subscriber', string='Subscriber', ondelete='cascade',
        index=True)
    direction = fields.Selection([
        ('in', 'Incoming'),
        ('out', 'Outgoing'),
    ], required=True, default='out', index=True)
    body = fields.Text(string='Message')
    message_type = fields.Selection([
        ('text', 'Text'),
        ('audio', 'Voice'),
        ('image', 'Image'),
        ('attachment', 'Attachment'),
        ('postback', 'Button Click'),
        ('comment', 'Comment'),
    ], default='text', required=True)
    is_bot = fields.Boolean(
        string='Automated',
        help="Sent automatically by a flow (as opposed to a manual reply).")
    error = fields.Char(
        help="Error returned by the Facebook Send API, when the message "
             "could not be delivered.")
