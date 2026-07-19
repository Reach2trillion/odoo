# Part of the sms_infobip module. License LGPL-3.

import logging
import re
from uuid import uuid4

import requests

from odoo.addons.sms.tools.sms_api import SmsApiBase
from odoo.tools import str2bool
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

INFOBIP_SEND_ENDPOINT = '/sms/2/text/advanced'
INFOBIP_TIMEOUT = 30  # seconds; batches can hold up to 500 destinations


class SmsApiInfobip(SmsApiBase):
    """Send Odoo SMS through the Infobip HTTP API (https://www.infobip.com/docs/sms).

    Plugged into the standard Odoo 18 SMS framework through
    ``res.company._get_sms_api_class()`` and ``sms.sms._split_by_api()``, so it
    transparently covers everything built on ``sms.sms``: CRM, Contacts,
    SMS Marketing, server actions, ...

    The Infobip ``messageId`` of every destination is set to the ``sms.sms``
    UUID, so send responses and delivery report webhooks map back to Odoo
    records without any extra storage.
    """

    # Provider states (returned by _send_sms_batch) -> sms.sms.failure_type.
    # Any state absent from this mapping ends up as failure_type 'unknown' and
    # its human readable 'failure_reason' is displayed on the notification.
    PROVIDER_TO_SMS_FAILURE_TYPE = SmsApiBase.PROVIDER_TO_SMS_FAILURE_TYPE | {
        'country_not_supported': 'sms_country_not_supported',
        'duplicate_message': 'sms_duplicate',
        'insufficient_credit': 'sms_credit',
        'registration_needed': 'sms_registration_needed',
        'unregistered': 'sms_acc',
    }

    # ------------------------------------------------------------------
    # Configuration helpers (usable as classmethods from models/controllers)
    # ------------------------------------------------------------------

    @classmethod
    def _get_param(cls, env, name, default=None):
        return env['ir.config_parameter'].sudo().get_param('sms_infobip.%s' % name, default)

    @classmethod
    def _is_enabled(cls, env):
        return str2bool(cls._get_param(env, 'enabled') or 'False', False)

    @classmethod
    def _get_infobip_base_url(cls, env):
        """Return the account-specific API base url, e.g. https://xxxxx.api.infobip.com"""
        base_url = (cls._get_param(env, 'base_url') or '').strip().rstrip('/')
        if base_url and '://' not in base_url:
            base_url = 'https://%s' % base_url
        return base_url

    @classmethod
    def _get_webhook_url(cls, env, force=False):
        """URL Infobip pushes delivery reports to (``notifyUrl``).

        Protected by a random token; generated once and kept in a config
        parameter. Returns False when delivery reports are disabled, unless
        ``force`` is set (used to display the URL in the settings).
        """
        if not force and not str2bool(cls._get_param(env, 'delivery_reports') or 'True', True):
            return False
        icp = env['ir.config_parameter'].sudo()
        token = icp.get_param('sms_infobip.webhook_token')
        if not token:
            token = uuid4().hex
            icp.set_param('sms_infobip.webhook_token', token)
        base_url = (icp.get_param('web.base.url') or '').rstrip('/')
        if not base_url:
            return False
        return '%s/sms_infobip/status/%s' % (base_url, token)

    def _format_number(self, number):
        """Normalize a phone number to Infobip's expected international format
        (digits only, with country code, no leading ``+``/``00``).

        Local numbers starting with a single 0 (e.g. Cambodian ``012 345 678``)
        get the configured default country prefix (855 by default).
        """
        number = re.sub(r'[^\d+]', '', number or '')
        if number.startswith('+'):
            number = number[1:].lstrip('0') if number[1:3] == '00' else number[1:]
        elif number.startswith('00'):
            number = number[2:]
        elif number.startswith('0'):
            default_cc = re.sub(r'\D', '', self._get_param(self.env, 'default_country_code', '855') or '')
            number = default_cc + number[1:] if default_cc else number
        return number

    # ------------------------------------------------------------------
    # SMS framework API
    # ------------------------------------------------------------------

    def _send_sms_batch(self, messages, delivery_reports_url=False):
        """Send SMS through Infobip in batch mode.

        :param list messages: [{'content': str,
                                'numbers': [{'uuid': str, 'number': str}, ...]}]
        :param str delivery_reports_url: standard Odoo/IAP report url, unused —
            Infobip pushes reports to our own ``/sms_infobip/status`` route.
        :return: [{'uuid': str, 'state': str, 'failure_reason': str (optional)}]
        """
        env = self.env
        all_uuids = [number['uuid'] for message in messages for number in message['numbers']]

        api_key = (self._get_param(env, 'api_key') or '').strip()
        base_url = self._get_infobip_base_url(env)
        if not api_key or not base_url:
            _logger.warning("Infobip SMS: missing API key or base URL, %d SMS not sent", len(all_uuids))
            return self._results_for_all(all_uuids, 'unregistered', _(
                "Infobip is not fully configured: set the API Base URL and API Key in "
                "Settings > Infobip SMS."))

        sender = (self._get_param(env, 'sender') or 'InfoSMS').strip()
        notify_url = self._get_webhook_url(env)

        payload_messages = []
        for message in messages:
            entry = {
                'from': sender,
                'destinations': [{
                    'to': self._format_number(number['number']),
                    'messageId': number['uuid'],
                } for number in message['numbers']],
                'text': message['content'] or '',
            }
            if notify_url:
                entry.update({
                    'notifyUrl': notify_url,
                    'notifyContentType': 'application/json',
                    'intermediateReport': False,
                })
            payload_messages.append(entry)

        try:
            response = requests.post(
                base_url + INFOBIP_SEND_ENDPOINT,
                json={'messages': payload_messages},
                headers={'Authorization': 'App %s' % api_key, 'Accept': 'application/json'},
                timeout=INFOBIP_TIMEOUT,
            )
        except requests.exceptions.RequestException as error:
            _logger.warning("Infobip SMS: could not reach the Infobip API at %s: %s", base_url, error)
            return self._results_for_all(all_uuids, 'server_error',
                                         _("Could not reach the Infobip API: %s", error))

        if response.status_code in (401, 403):
            _logger.warning("Infobip SMS: authentication failed (HTTP %s)", response.status_code)
            return self._results_for_all(all_uuids, 'unregistered',
                                         _("Infobip rejected the API Key (HTTP %s). Check it in Settings > Infobip SMS.",
                                           response.status_code))
        if response.status_code >= 400:
            reason = self._extract_request_error(response)
            _logger.warning("Infobip SMS: request rejected (HTTP %s): %s", response.status_code, reason)
            return self._results_for_all(all_uuids, 'server_error', reason)

        try:
            data = response.json()
        except ValueError:
            _logger.warning("Infobip SMS: unreadable response: %s", response.text[:500])
            return self._results_for_all(all_uuids, 'server_error', _("Unreadable response from Infobip."))

        expected_uuids = set(all_uuids)
        results, seen_uuids = [], set()
        for message in data.get('messages') or []:
            uuid = message.get('messageId')
            if uuid not in expected_uuids or uuid in seen_uuids:
                continue
            seen_uuids.add(uuid)
            state, failure_reason = self._map_send_status(message.get('status') or {})
            result = {'uuid': uuid, 'state': state}
            if failure_reason:
                result['failure_reason'] = failure_reason
            results.append(result)
        # Defensive: a status for every SMS we were asked to send
        results += self._results_for_all(
            [uuid for uuid in all_uuids if uuid not in seen_uuids],
            'server_error', _("No status returned by Infobip for this message."))

        sent = sum(1 for result in results if result['state'] == 'success')
        _logger.info("Infobip SMS: batch of %d SMS handed over, %d accepted", len(all_uuids), sent)
        return results

    def _get_sms_api_error_messages(self):
        """Infobip-specific wording for error states (shown in SMS Marketing
        and message notifications instead of the IAP messages)."""
        error_dict = super()._get_sms_api_error_messages()
        error_dict.update({
            'unregistered': _("Your Infobip API Key / Base URL is missing or invalid (Settings > Infobip SMS)."),
            'insufficient_credit': _("Your Infobip account balance is too low. Top it up on portal.infobip.com."),
            'wrong_number_format': _("The recipient number is invalid. Use the international format, e.g. +855 12 345 678."),
            'country_not_supported': _("This destination is not enabled on your Infobip account."),
            'registration_needed': _("Your sender ID is not allowed for this destination. Register it on the Infobip portal."),
            'duplicate_message': _("Infobip flagged this message as a duplicate."),
            'server_error': _("Infobip could not process the message. Check the Odoo server log for details."),
        })
        return error_dict

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _results_for_all(uuids, state, failure_reason=None):
        result = {'state': state}
        if failure_reason:
            result['failure_reason'] = failure_reason
        return [dict(result, uuid=uuid) for uuid in uuids]

    @staticmethod
    def _extract_request_error(response):
        try:
            exception = response.json()['requestError']['serviceException']
            return '%s: %s' % (exception.get('messageId'), exception.get('text'))
        except (ValueError, KeyError, TypeError):
            return (response.text or '')[:200] or 'HTTP %s' % response.status_code

    @staticmethod
    def _map_send_status(status):
        """Map an Infobip send status (https://www.infobip.com/docs/essentials/response-status-and-error-codes)
        to the provider states understood by ``sms.sms._send_with_api()``.

        :return: (state, failure_reason or None)
        """
        group = (status.get('groupName') or '').upper()
        name = (status.get('name') or '').upper()
        description = status.get('description') or (status.get('name') or '')
        if group in ('PENDING', 'DELIVERED'):
            return 'success', None
        if 'NOT_ENOUGH_CREDITS' in name or 'PREPAID_PACKAGE_EXPIRED' in name:
            return 'insufficient_credit', description
        if 'DESTINATION_ADDRESS' in name or 'PREFIX_MISSING' in name:
            return 'wrong_number_format', description
        if 'DESTINATION_NOT_REGISTERED' in name:
            # Free trial accounts may only message verified numbers
            return 'unregistered', description
        if 'SENDER' in name or 'SOURCE' in name:
            return 'registration_needed', description
        if 'ROUTE_NOT_AVAILABLE' in name or 'NETWORK' in name or name == 'REJECTED_DESTINATION':
            return 'country_not_supported', description
        if 'DUPLICATE' in name:
            return 'duplicate_message', description
        if 'SYSTEM_ERROR' in name or not name:
            return 'server_error', description
        # Unmapped rejection: keep Infobip's status name as the state so it is
        # reported as an 'unknown' failure with the description as reason.
        return name.lower(), description
