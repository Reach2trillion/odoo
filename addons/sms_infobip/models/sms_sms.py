# Part of the sms_infobip module. License LGPL-3.

import logging

from odoo import models, tools

from ..tools.sms_api_infobip import SmsApiInfobip

try:
    from odoo.addons.sms.tools.sms_api import SmsApi
except ImportError:  # very old/new core layout; only needed for IAP fallback
    SmsApi = None

_logger = logging.getLogger(__name__)

# provider state -> sms.sms state, as used by every Odoo 18.0 build
# (fallback in case IAP_TO_SMS_STATE_SUCCESS ever disappears from core)
PROVIDER_STATE_SUCCESS = {
    'processing': 'process',
    'success': 'pending',
    'sent': 'pending',
    'delivered': 'sent',
}


class SmsSms(models.Model):
    _inherit = 'sms.sms'

    def _split_by_api(self):
        # Recent 18.0 builds: send() asks this generator which API client to
        # use; the base implementation always yields the IAP one.
        if SmsApiInfobip._is_enabled(self.env):
            yield SmsApiInfobip(self.env), self
        elif hasattr(super(), '_split_by_api'):
            yield from super()._split_by_api()
        elif SmsApi is not None:  # early 18.0: nothing calls this, stay coherent anyway
            yield SmsApi(self.env), self
        else:
            yield SmsApiInfobip(self.env), self

    def _send(self, unlink_failed=False, unlink_sent=True, raise_exception=False):
        # Recent 18.0 builds route through the pluggable framework
        # (_send_with_api + _split_by_api/_get_sms_api_class overrides).
        # Early 18.0 builds hardcode the IAP client inside _send(), so take
        # over the whole send flow here instead.
        if hasattr(self, '_send_with_api') or not SmsApiInfobip._is_enabled(self.env):
            return super()._send(unlink_failed=unlink_failed, unlink_sent=unlink_sent,
                                 raise_exception=raise_exception)
        return self._send_infobip(unlink_failed=unlink_failed, unlink_sent=unlink_sent,
                                  raise_exception=raise_exception)

    def _send_infobip(self, unlink_failed=False, unlink_sent=True, raise_exception=False):
        """Replicate the standard ``_send()`` flow with the Infobip client, for
        Odoo 18.0 builds that predate the pluggable sms_api framework."""
        if not self:
            return True
        messages = [{
            'content': body,
            'numbers': [{'number': sms.number, 'uuid': sms.uuid} for sms in body_sms_records],
        } for body, body_sms_records in self.grouped('body').items()]

        try:
            results = SmsApiInfobip(self.env)._send_sms_batch(messages)
        except Exception as e:
            _logger.info('Sent batch %s SMS: %s: failed with exception %s', len(self.ids), self.ids, e)
            if raise_exception:
                raise
            results = [{'uuid': sms.uuid, 'state': 'server_error'} for sms in self]
        else:
            _logger.info('Send batch %s SMS: %s: gave %s', len(self.ids), self.ids, results)

        results_uuids = [result['uuid'] for result in results]
        all_sms_sudo = self.env['sms.sms'].sudo().search(
            [('uuid', 'in', results_uuids)]).with_context(sms_skip_msg_notification=True)
        success_states = getattr(self, 'IAP_TO_SMS_STATE_SUCCESS', None) or PROVIDER_STATE_SUCCESS

        groups = tools.groupby(results, key=lambda result: (result['state'], result.get('failure_reason')))
        for (state, failure_reason), results_group in groups:
            group_uuids = {result['uuid'] for result in results_group}
            sms_sudo = all_sms_sudo.filtered(lambda s: s.uuid in group_uuids)
            if success_state := success_states.get(state):
                sms_sudo.sms_tracker_id._action_update_from_sms_state(success_state)
                to_delete = {'to_delete': True} if unlink_sent else {}
                sms_sudo.write({'state': success_state, 'failure_type': False, **to_delete})
            else:
                failure_type = SmsApiInfobip.PROVIDER_TO_SMS_FAILURE_TYPE.get(state, 'unknown')
                if failure_type != 'unknown':
                    sms_sudo.sms_tracker_id._action_update_from_sms_state(
                        'error', failure_type=failure_type, failure_reason=failure_reason)
                else:
                    sms_sudo.sms_tracker_id.with_context(
                        sms_known_failure_reason=failure_reason,
                    )._action_update_from_provider_error(state)
                to_delete = {'to_delete': True} if unlink_failed else {}
                sms_sudo.write({'state': 'error', 'failure_type': failure_type, **to_delete})

        all_sms_sudo.mail_message_id._notify_message_notification_update()
        return True
