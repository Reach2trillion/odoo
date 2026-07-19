# Part of the sms_infobip module. License LGPL-3.

from unittest.mock import patch

from odoo.addons.sms_infobip.tools.sms_api_infobip import SmsApiInfobip
from odoo.tests import TransactionCase, tagged


class MockResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = ''

    def json(self):
        return self._payload


def _accept_all(url, json=None, headers=None, timeout=None):
    """Fake Infobip endpoint accepting every destination (PENDING)."""
    return MockResponse(200, {'messages': [
        {
            'to': destination['to'],
            'messageId': destination['messageId'],
            'status': {'groupId': 1, 'groupName': 'PENDING', 'id': 26,
                       'name': 'PENDING_ACCEPTED', 'description': 'Message sent to next instance'},
        }
        for message in json['messages'] for destination in message['destinations']
    ]})


@tagged('post_install', '-at_install')
class TestSmsInfobip(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env['ir.config_parameter'].sudo()
        icp.set_param('sms_infobip.enabled', 'True')
        icp.set_param('sms_infobip.base_url', 'https://unittest.api.infobip.com')
        icp.set_param('sms_infobip.api_key', 'test-key')
        icp.set_param('sms_infobip.sender', 'TestSender')
        icp.set_param('sms_infobip.default_country_code', '855')
        icp.set_param('sms_infobip.delivery_reports', 'False')

    def test_number_formatting(self):
        api = SmsApiInfobip(self.env)
        self.assertEqual(api._format_number('+855 12 345 678'), '85512345678')
        self.assertEqual(api._format_number('012 345 678'), '85512345678')
        self.assertEqual(api._format_number('0085512345678'), '85512345678')
        self.assertEqual(api._format_number('85512345678'), '85512345678')

    def test_company_uses_infobip_api(self):
        self.assertIs(self.env.company._get_sms_api_class(), SmsApiInfobip)
        self.env['ir.config_parameter'].sudo().set_param('sms_infobip.enabled', 'False')
        self.assertIsNot(self.env.company._get_sms_api_class(), SmsApiInfobip)

    def test_send_success(self):
        sms = self.env['sms.sms'].create({'number': '+855 12 345 678', 'body': 'Chum reap sour!'})
        calls = []

        def fake_post(url, json=None, headers=None, timeout=None):
            calls.append((url, json, headers))
            return _accept_all(url, json=json, headers=headers, timeout=timeout)

        with patch('odoo.addons.sms_infobip.tools.sms_api_infobip.requests.post', side_effect=fake_post):
            sms.send(unlink_failed=False, unlink_sent=False, raise_exception=True)

        self.assertEqual(sms.state, 'pending', "Accepted SMS must be marked as sent (pending delivery report)")
        url, payload, headers = calls[0]
        self.assertIn('/sms/2/text/advanced', url)
        self.assertEqual(headers['Authorization'], 'App test-key')
        self.assertEqual(payload['messages'][0]['from'], 'TestSender')
        self.assertEqual(payload['messages'][0]['destinations'][0]['to'], '85512345678')
        self.assertEqual(payload['messages'][0]['destinations'][0]['messageId'], sms.uuid)

    def test_send_rejected_credits(self):
        sms = self.env['sms.sms'].create({'number': '+85512345678', 'body': 'Test'})

        def fake_post(url, json=None, headers=None, timeout=None):
            return MockResponse(200, {'messages': [{
                'to': destination['to'],
                'messageId': destination['messageId'],
                'status': {'groupId': 5, 'groupName': 'REJECTED', 'id': 9,
                           'name': 'REJECTED_NOT_ENOUGH_CREDITS', 'description': 'Not enough credits'},
            } for message in json['messages'] for destination in message['destinations']]})

        with patch('odoo.addons.sms_infobip.tools.sms_api_infobip.requests.post', side_effect=fake_post):
            sms.send(unlink_failed=False, unlink_sent=False, raise_exception=True)

        self.assertEqual(sms.state, 'error')
        self.assertEqual(sms.failure_type, 'sms_credit')

    def test_send_auth_error(self):
        sms = self.env['sms.sms'].create({'number': '+85512345678', 'body': 'Test'})

        with patch('odoo.addons.sms_infobip.tools.sms_api_infobip.requests.post',
                   return_value=MockResponse(401, {})):
            sms.send(unlink_failed=False, unlink_sent=False, raise_exception=True)

        self.assertEqual(sms.state, 'error')
        self.assertEqual(sms.failure_type, 'sms_acc')

    def test_not_configured(self):
        self.env['ir.config_parameter'].sudo().set_param('sms_infobip.api_key', '')
        sms = self.env['sms.sms'].create({'number': '+85512345678', 'body': 'Test'})
        # No mock: the code must not attempt any HTTP call without credentials
        sms.send(unlink_failed=False, unlink_sent=False, raise_exception=True)
        self.assertEqual(sms.state, 'error')
        self.assertEqual(sms.failure_type, 'sms_acc')
