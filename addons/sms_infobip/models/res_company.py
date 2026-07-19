# Part of the sms_infobip module. License LGPL-3.

from odoo import models

from ..tools.sms_api_infobip import SmsApiInfobip

try:
    from odoo.addons.sms.tools.sms_api import SmsApi
except ImportError:  # tolerate future core layout changes
    SmsApi = None


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _get_sms_api_class(self):
        # Hook of recent Odoo 18.0 builds; early builds don't define nor call
        # it (they are handled by the sms.sms._send() override), but keep the
        # method coherent on every build.
        self.ensure_one()
        if SmsApiInfobip._is_enabled(self.env):
            return SmsApiInfobip
        if hasattr(super(), '_get_sms_api_class'):
            return super()._get_sms_api_class()
        return SmsApi or SmsApiInfobip
