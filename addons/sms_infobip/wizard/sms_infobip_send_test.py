# Part of the sms_infobip module. License LGPL-3.

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..tools.sms_api_infobip import SmsApiInfobip


class SmsInfobipSendTest(models.TransientModel):
    _name = 'sms_infobip.send.test'
    _description = 'Send a test SMS through Infobip'

    number = fields.Char(
        "Phone Number", required=True,
        help="International format preferred, e.g. +855 12 345 678. A local number "
             "starting with 0 gets the configured default country prefix.")
    body = fields.Text(
        "Message", required=True,
        default=lambda self: _("Infobip is connected to Odoo — test message."))

    def action_send(self):
        self.ensure_one()
        if not SmsApiInfobip._is_enabled(self.env):
            raise UserError(_("Enable and save 'Send SMS via Infobip' in the settings first."))

        sms = self.env['sms.sms'].sudo().create({'number': self.number, 'body': self.body})
        sms.send(unlink_failed=False, unlink_sent=False, raise_exception=True)

        if sms.state == 'error':
            failure_labels = dict(sms._fields['failure_type']._description_selection(self.env))
            api_errors = SmsApiInfobip(self.env)._get_sms_api_error_messages()
            provider_state = {ft: state for state, ft in SmsApiInfobip.PROVIDER_TO_SMS_FAILURE_TYPE.items()}
            detail = api_errors.get(provider_state.get(sms.failure_type), '')
            raise UserError(_(
                "The test SMS could not be sent: %(failure)s\n%(detail)s\n"
                "More details may be available in the Odoo server log.",
                failure=failure_labels.get(sms.failure_type) or sms.failure_type or _("Unknown error"),
                detail=detail,
            ))

        state_labels = dict(sms._fields['state']._description_selection(self.env))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _("Test SMS handed over to Infobip"),
                'message': _("Current status: %s — delivery reports will update it shortly.",
                             state_labels.get(sms.state, sms.state)),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
