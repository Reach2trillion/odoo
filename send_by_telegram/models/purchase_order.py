# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_send_telegram(self):
        """Open wizard to send RFQ/PO via Telegram."""
        self.ensure_one()
        
        # Check if partner has Telegram group ID
        if not self.partner_id.telegram_group_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Warning"),
                    'message': _("Vendor '%s' does not have a Telegram Group ID configured.") 
                               % self.partner_id.name,
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
                'default_res_model': 'purchase.order',
                'default_res_id': self.id,
                'default_partner_id': self.partner_id.id,
                'mark_rfq_as_sent': True,
            }
        }
    
    def _get_telegram_document_name(self):
        """Get PDF document name for Telegram in current language.
        
        Returns:
            str: Localized filename for the PDF
        """
        self.ensure_one()
        if self.state in ['draft', 'sent']:
            return _("RFQ_%s.pdf") % self.name
        return _("PurchaseOrder_%s.pdf") % self.name
    
    def _get_telegram_message_text(self):
        """Get message text for Telegram in current language.
        
        Returns:
            str: Localized message text
        """
        self.ensure_one()
        if self.state in ['draft', 'sent']:
            doc_type = _("Request for Quotation")
        else:
            doc_type = _("Purchase Order")
            
        return _(
            "Dear %(partner)s,\n\n"
            "Your %(doc_type)s is ready, reference: <b>%(order)s</b>.\n"
            "PDF document is attached.\n\n"
            "Best regards"
        ) % {
            'partner': self.partner_id.name,
            'doc_type': doc_type,
            'order': self.name,
        }
