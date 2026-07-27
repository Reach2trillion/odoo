# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class ChatflowSendMessage(models.TransientModel):
    _name = 'chatflow.send.message'
    _description = 'Send a Manual Messenger Reply'

    subscriber_id = fields.Many2one(
        'chatflow.subscriber', required=True, ondelete='cascade')
    in_24h_window = fields.Boolean(
        related='subscriber_id.in_24h_window')
    message = fields.Text(required=True)
    send_voice = fields.Boolean(
        string='Also Send as Voice',
        help="Additionally send the message as a text-to-speech voice "
             "message (requires the gtts package on the server).")

    def action_send(self):
        self.ensure_one()
        subscriber = self.subscriber_id
        page = subscriber.page_id
        ok = page._send_message(
            subscriber, {'text': self.message}, self.message,
            message_type='text', is_bot=False)
        if not ok:
            raise UserError(_(
                "Facebook rejected the message. Standard replies are only "
                "allowed within 24 hours of the subscriber's last message. "
                "See the message log for the exact error."))
        if self.send_voice:
            attachment_id = page._get_voice_attachment(self.message)
            if attachment_id:
                page._send_message(
                    subscriber,
                    {'attachment': {
                        'type': 'audio',
                        'payload': {'attachment_id': attachment_id},
                    }},
                    self.message, message_type='audio', is_bot=False)
        return {'type': 'ir.actions.act_window_close'}
