# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models

from ..services.telegram_service import TelegramService


class MailMessage(models.Model):
    _inherit = 'mail.message'

    is_telegram_message = fields.Boolean(
        string="Sent via Telegram",
        default=False,
        help="Indicates if this message was sent via Telegram"
    )


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def action_send_telegram_from_chatter(self):
        """Open wizard to send a message via Telegram from chatter."""
        self.ensure_one()
        
        # Get partner based on model
        partner = False
        if hasattr(self, 'partner_id') and self.partner_id:
            partner = self.partner_id
        
        if not partner or not partner.telegram_group_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Warning"),
                    'message': _("No Telegram Group ID configured for this record's partner."),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        return {
            'name': _("Send via Telegram"),
            'type': 'ir.actions.act_window',
            'res_model': 'telegram.message.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
                'default_partner_id': partner.id,
                'default_send_document': False,  # Only message from chatter
            }
        }

    def _telegram_post_message(self, body, partner_id=None):
        """Post a message to chatter indicating it was sent via Telegram.
        
        Args:
            body (str): Message body that was sent
            partner_id (int): Optional partner ID
        """
        self.ensure_one()
        self.message_post(
            body=_("📱 <b>Sent via Telegram:</b><br/>%s") % body,
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )
