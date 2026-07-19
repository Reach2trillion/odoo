# Part of the sms_infobip module. License LGPL-3.

import json
import logging
import re

from werkzeug.exceptions import Forbidden

from odoo.http import Controller, request, route
from odoo.tools import consteq

_logger = logging.getLogger(__name__)

# sms.sms uuids are uuid4().hex — anything else is not ours
UUID_RE = re.compile(r'^[0-9a-f]{32}$')

# Infobip delivery report status groups
# (https://www.infobip.com/docs/essentials/response-status-and-error-codes)
SUCCESS_GROUP_TO_SMS_STATE = {
    'DELIVERED': 'sent',     # sms.sms state 'sent' is displayed as "Delivered"
    'PENDING': 'pending',    # still with the operator; displayed as "Sent"
}
ERROR_GROUP_TO_PROVIDER_ERROR = {
    'EXPIRED': 'expired',
    'UNDELIVERABLE': 'not_delivered',
    'REJECTED': 'rejected',
}


class SmsInfobipController(Controller):

    @route('/sms_infobip/status/<string:token>', type='http', auth='public',
           methods=['POST'], csrf=False)
    def sms_infobip_delivery_report(self, token, **kwargs):
        """Receive Infobip delivery reports (``notifyUrl`` callbacks).

        Payload: ``{"results": [{"messageId": <sms.sms uuid>, "status": {...},
        "error": {...}, ...}, ...]}``. Updates the SMS trackers (chatter
        notifications / mailing traces) exactly like the standard IAP
        ``/sms/status`` controller does.
        """
        expected_token = request.env['ir.config_parameter'].sudo().get_param('sms_infobip.webhook_token')
        if not expected_token or not consteq(expected_token, token):
            raise Forbidden()

        try:
            payload = json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except ValueError:
            _logger.warning("Infobip DLR: received invalid JSON payload")
            return request.make_json_response({'error': 'invalid JSON payload'}, status=400)
        results = payload.get('results')
        if not isinstance(results, list):
            return request.make_json_response({'error': "missing 'results' list"}, status=400)

        grouped = {}
        for result in results:
            if not isinstance(result, dict):
                continue
            uuid = result.get('messageId')
            if not isinstance(uuid, str) or not UUID_RE.match(uuid):
                continue  # not an Odoo-generated message id
            status = result.get('status') or {}
            error = result.get('error') or {}
            group = (status.get('groupName') or '').upper()
            description = status.get('description')
            if error.get('id'):  # 0 / NO_ERROR when everything is fine
                description = error.get('description') or description
            grouped.setdefault((group, description), []).append(uuid)

        for (group, description), uuids in grouped.items():
            trackers_sudo = request.env['sms.tracker'].sudo().search([('sms_uuid', 'in', uuids)])
            sms_sudo = request.env['sms.sms'].sudo().search([('uuid', 'in', uuids)])
            if sms_state := SUCCESS_GROUP_TO_SMS_STATE.get(group):
                trackers_sudo._action_update_from_sms_state(sms_state)
                sms_sudo.filtered(lambda sms: sms.state != 'sent').write(
                    {'state': sms_state, 'failure_type': False})
            elif provider_error := ERROR_GROUP_TO_PROVIDER_ERROR.get(group):
                trackers_sudo.with_context(
                    sms_known_failure_reason=description or '',
                )._action_update_from_provider_error(provider_error)
                sms_sudo.write({'state': 'error', 'failure_type': 'unknown'})
            else:
                _logger.info("Infobip DLR: ignored unknown status group %r for %d message(s)",
                             group, len(uuids))
                continue
            _logger.info("Infobip DLR: %d message(s) updated to %s%s", len(uuids), group,
                         ' (%s)' % description if description else '')

        return request.make_json_response({'status': 'ok'})
