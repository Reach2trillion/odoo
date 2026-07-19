# Part of the sms_infobip module. License LGPL-3.

from odoo import models

from ..tools.sms_api_infobip import SmsApiInfobip


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _get_sms_api_class(self):
        self.ensure_one()
        if SmsApiInfobip._is_enabled(self.env):
            return SmsApiInfobip
        return super()._get_sms_api_class()
