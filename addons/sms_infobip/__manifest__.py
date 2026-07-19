# Part of the sms_infobip module. License LGPL-3.
{
    'name': 'Infobip SMS Connector',
    'version': '18.0.1.0.0',
    'category': 'Marketing',
    'summary': 'Send Odoo SMS (CRM, SMS Marketing, ...) through Infobip — ideal for Cambodia (+855)',
    'description': """
Route every SMS sent by Odoo through your own Infobip account
(https://www.infobip.com/sms/api) instead of the Odoo IAP SMS service.

Works transparently with every feature built on the standard SMS framework:
CRM (send SMS to leads/customers, SMS activities), Contacts, Sales,
SMS Marketing (mass_mailing_sms), automation rules, ...

Highlights
----------
* Uses the official Infobip HTTP API (POST /sms/2/text/advanced)
* Delivery reports pushed back to Odoo (Delivered / Undelivered / Rejected)
* Custom sender ID (register your brand name for Cambodian operators)
* Local number normalization with a configurable default country prefix
  (855 — Cambodia — out of the box)
* "Send test SMS" wizard in Settings
* Falls back to the standard Odoo IAP service when disabled
""",
    'author': 'reach2trillion',
    'website': 'https://github.com/reach2trillion/odoo',
    'license': 'LGPL-3',
    'depends': ['sms', 'base_setup'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'wizard/sms_infobip_send_test_views.xml',
    ],
    'application': False,
    'installable': True,
}
