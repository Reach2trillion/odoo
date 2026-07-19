# Part of the sms_infobip module. License LGPL-3.

from odoo import _, api, fields, models

from ..tools.sms_api_infobip import SmsApiInfobip


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sms_infobip_enabled = fields.Boolean(
        "Send SMS via Infobip", config_parameter='sms_infobip.enabled',
        help="Route all SMS sent by Odoo (CRM, SMS Marketing, ...) through your "
             "Infobip account. When disabled, Odoo uses the standard IAP SMS service.")
    sms_infobip_base_url = fields.Char(
        "API Base URL", config_parameter='sms_infobip.base_url',
        help="Your account-specific base URL shown on the Infobip portal homepage, "
             "e.g. https://xxxxx.api.infobip.com")
    sms_infobip_api_key = fields.Char(
        "API Key", config_parameter='sms_infobip.api_key',
        help="API key created on portal.infobip.com (Developer Tools > API Keys).")
    sms_infobip_sender = fields.Char(
        "Sender ID", config_parameter='sms_infobip.sender', default='InfoSMS',
        help="Alphanumeric sender name (3-11 characters, e.g. your brand) or a phone number. "
             "For Cambodian operators (Smart, Cellcard, Metfone), register your sender ID "
             "with Infobip for reliable delivery.")
    sms_infobip_default_country_code = fields.Char(
        "Default Country Prefix", config_parameter='sms_infobip.default_country_code',
        default='855',
        help="Country calling code (without +) prepended to local numbers written with a "
             "leading 0, e.g. 012 345 678 -> +855 12 345 678. Default: 855 (Cambodia).")
    sms_infobip_delivery_reports = fields.Boolean(
        "Delivery Reports", config_parameter='sms_infobip.delivery_reports', default=True,
        help="Let Infobip push delivery reports back to Odoo so messages show as "
             "Delivered / Failed. Your Odoo must be reachable from the internet.")
    sms_infobip_webhook_url = fields.Char(
        "Delivery Report URL", compute='_compute_sms_infobip_webhook_url',
        help="Reports are requested automatically on every send; you can also configure "
             "this URL on your Infobip API key as a fallback.")

    @api.depends('sms_infobip_delivery_reports')
    def _compute_sms_infobip_webhook_url(self):
        url = SmsApiInfobip._get_webhook_url(self.env, force=True)
        for settings in self:
            settings.sms_infobip_webhook_url = url or False

    def action_sms_infobip_send_test(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Send Test SMS via Infobip"),
            'res_model': 'sms_infobip.send.test',
            'view_mode': 'form',
            'target': 'new',
        }
