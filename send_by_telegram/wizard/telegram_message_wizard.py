# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services.telegram_service import TelegramService

_logger = logging.getLogger(__name__)


class TelegramMessageWizard(models.TransientModel):
    _name = 'telegram.message.wizard'
    _description = 'Send Message via Telegram'

    res_model = fields.Char(string="Related Model", required=True)
    res_id = fields.Integer(string="Related Record ID", required=True)
    partner_id = fields.Many2one('res.partner', string="Recipient", required=True)
    message = fields.Text(string="Message", required=True)
    
    # For sale/purchase orders - attach PDF report
    send_pdf_report = fields.Boolean(string="Attach PDF Report", default=False)
    
    # For chatter - attach any file
    attachment_ids = fields.Many2many(
        'ir.attachment', 
        string="Attachments",
        help="Attach files to send via Telegram"
    )
    
    # Mode: 'order' for sale/purchase, 'chatter' for chatter
    mode = fields.Selection([
        ('order', 'Order'),
        ('chatter', 'Chatter'),
    ], default='order')
    
    @api.model
    def default_get(self, fields_list):
        """Set default values based on the related record."""
        res = super().default_get(fields_list)
        
        res_model = self.env.context.get('default_res_model')
        res_id = self.env.context.get('default_res_id')
        
        # Determine mode based on context
        if self.env.context.get('from_chatter'):
            res['mode'] = 'chatter'
            res['send_pdf_report'] = False
        else:
            res['mode'] = 'order'
            res['send_pdf_report'] = True
        
        if res_model and res_id:
            record = self.env[res_model].browse(res_id)
            
            # Get partner_id from sale.order or purchase.order
            if not res.get('partner_id'):
                if res_model == 'sale.order' and hasattr(record, 'partner_id'):
                    res['partner_id'] = record.partner_id.id
                elif res_model == 'purchase.order' and hasattr(record, 'partner_id'):
                    res['partner_id'] = record.partner_id.id
            
            # Get default message
            if hasattr(record, '_get_telegram_message_text'):
                res['message'] = record._get_telegram_message_text()
            elif res.get('mode') == 'chatter':
                # Simple default message for chatter
                res['message'] = ""
        
        return res
    
    def _get_telegram_service(self):
        """Get configured Telegram service instance."""
        token = self.env['ir.config_parameter'].sudo().get_param(
            'send_by_telegram.bot_token'
        )
        if not token:
            raise UserError(
                _("Telegram bot token is not configured. "
                  "Please go to Settings → General Settings → Send by Telegram.")
            )
        return TelegramService(token)
    
    def _get_report_pdf(self):
        """Generate PDF report for the related record."""
        record = self.env[self.res_model].browse(self.res_id)
        
        # Determine which report to use
        if self.res_model == 'sale.order':
            report_name = 'sale.report_saleorder'
        elif self.res_model == 'purchase.order':
            report_name = 'purchase.report_purchaseorder'
        else:
            raise UserError(_("PDF report is not available for this model."))
        
        # Generate PDF
        report = self.env['ir.actions.report']._get_report(report_name)
        pdf_content, _ = report._render_qweb_pdf(report_name, [self.res_id])
        
        # Get localized filename
        if hasattr(record, '_get_telegram_document_name'):
            filename = record._get_telegram_document_name()
        else:
            filename = f"{self.res_model}_{self.res_id}.pdf"
        
        return pdf_content, filename
    
    def _mark_as_sent(self):
        """Mark the related order as sent (change status)."""
        record = self.env[self.res_model].browse(self.res_id)
        
        if self.res_model == 'sale.order':
            if record.state == 'draft':
                record.write({'state': 'sent'})
        elif self.res_model == 'purchase.order':
            if record.state == 'draft':
                record.write({'state': 'sent'})
    
    def _post_to_chatter(self, attachment_ids=None):
        """Post a log message to the record's chatter with attachments."""
        record = self.env[self.res_model].browse(self.res_id)
        
        # Build simple subject
        subject = _("Sent via Telegram to %s") % self.partner_id.name
        
        body_parts = [
            "<p><em>%s</em></p>" % subject,
        ]
        
        if self.message:
            body_parts.append("<p>%s</p>" % self.message.replace('\n', '<br/>'))
        
        body = Markup("".join(body_parts))
        
        # Post message with attachments
        record.message_post(
            body=body,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
            attachment_ids=attachment_ids or [],
        )
    
    def action_send(self):
        """Send the message via Telegram."""
        self.ensure_one()
        
        # Validate Telegram group ID
        if not self.partner_id.telegram_group_id:
            raise UserError(
                _("Partner '%s' does not have a Telegram Group ID configured.") 
                % self.partner_id.name
            )
        
        chat_id = self.partner_id.telegram_group_id
        service = self._get_telegram_service()
        
        try:
            chatter_attachment_ids = []
            
            if self.send_pdf_report and self.res_model in ('sale.order', 'purchase.order'):
                # Send PDF report for orders
                pdf_content, filename = self._get_report_pdf()
                service.send_document(
                    chat_id=chat_id,
                    document_content=pdf_content,
                    filename=filename,
                    caption=self.message,
                )
                
                # Create attachment for chatter
                pdf_attachment = self.env['ir.attachment'].create({
                    'name': filename,
                    'type': 'binary',
                    'datas': base64.b64encode(pdf_content),
                    'res_model': self.res_model,
                    'res_id': self.res_id,
                    'mimetype': 'application/pdf',
                })
                chatter_attachment_ids.append(pdf_attachment.id)
                
            elif self.attachment_ids:
                # Send attachments (from chatter)
                # Check if we have images
                image_mimetypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
                
                # Separate images and other files
                images = self.attachment_ids.filtered(
                    lambda a: a.mimetype and a.mimetype in image_mimetypes
                )
                other_files = self.attachment_ids - images
                
                # Send images first (with caption on first image)
                first_image = True
                for attachment in images:
                    file_content = base64.b64decode(attachment.datas)
                    # First image gets the message as caption
                    caption = self.message if first_image and self.message else ""
                    service.send_photo(
                        chat_id=chat_id,
                        photo_content=file_content,
                        filename=attachment.name,
                        caption=caption,
                    )
                    first_image = False
                
                # Send other files as documents
                for attachment in other_files:
                    file_content = base64.b64decode(attachment.datas)
                    # If no images were sent, first file gets the caption
                    caption = ""
                    if not images and attachment == other_files[0] and self.message:
                        caption = self.message
                    service.send_document(
                        chat_id=chat_id,
                        document_content=file_content,
                        filename=attachment.name,
                        caption=caption,
                        mimetype=attachment.mimetype,
                    )
                
                # If no attachments at all but have message, send text
                if not images and not other_files and self.message:
                    service.send_message(chat_id=chat_id, text=self.message)
                
                # Use existing attachments for chatter
                chatter_attachment_ids = self.attachment_ids.ids
                
            else:
                # Send text message only
                service.send_message(chat_id=chat_id, text=self.message)
            
            # Mark order as sent if applicable
            if self.env.context.get('mark_so_as_sent') or self.env.context.get('mark_rfq_as_sent'):
                self._mark_as_sent()
            
            # Post to chatter with attachments
            self._post_to_chatter(attachment_ids=chatter_attachment_ids)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Success!"),
                    'message': _("Message sent successfully via Telegram!"),
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
            
        except UserError:
            raise
        except Exception as e:
            _logger.exception("Failed to send Telegram message")
            raise UserError(_("Failed to send message: %s") % str(e))
