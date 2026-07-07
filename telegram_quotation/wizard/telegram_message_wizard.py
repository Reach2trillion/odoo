# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

import requests

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot%s/sendDocument"


class TelegramMessageWizard(models.TransientModel):
    _name = 'telegram.message.wizard'
    _description = "Send Document via Telegram"

    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    partner_id = fields.Many2one('res.partner', required=True)
    telegram_group_id = fields.Char(related='partner_id.telegram_group_id', readonly=True)
    message = fields.Text(string="Message", required=True)

    def _get_record(self):
        self.ensure_one()
        return self.env[self.res_model].browse(self.res_id)

    def _get_bot_token(self):
        token = self.env['ir.config_parameter'].sudo().get_param('telegram_quotation.bot_token')
        if not token:
            raise UserError(_(
                "No Telegram bot token configured. Set the 'telegram_quotation.bot_token' "
                "system parameter in Settings > Technical > Parameters."
            ))
        return token

    def action_send(self):
        self.ensure_one()
        if not self.telegram_group_id:
            raise UserError(_("This customer does not have a Telegram Group ID configured."))

        record = self._get_record()
        token = self._get_bot_token()

        report_action = self.env.ref('sale.action_report_saleorder')
        pdf_content, _report_type = report_action._render_qweb_pdf(record.ids)
        filename = record._get_telegram_document_name()

        try:
            response = requests.post(
                TELEGRAM_API_URL % token,
                data={
                    'chat_id': self.telegram_group_id,
                    'caption': self.message,
                    'parse_mode': 'HTML',
                },
                files={'document': (filename, pdf_content, 'application/pdf')},
                timeout=15,
            )
            response.raise_for_status()
            result = response.json()
        except requests.RequestException as exc:
            _logger.exception("Telegram API call failed")
            raise UserError(_("Failed to reach Telegram: %s") % exc) from exc

        if not result.get('ok'):
            raise UserError(_("Telegram API error: %s") % result.get('description'))

        if self.env.context.get('mark_so_as_sent') and hasattr(record, 'state') and record.state == 'draft':
            record.write({'state': 'sent'})

        return {'type': 'ir.actions.act_window_close'}
