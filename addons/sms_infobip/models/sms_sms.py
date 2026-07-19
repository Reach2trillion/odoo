# Part of the sms_infobip module. License LGPL-3.

from odoo import models

from ..tools.sms_api_infobip import SmsApiInfobip


class SmsSms(models.Model):
    _inherit = 'sms.sms'

    def _split_by_api(self):
        # The base implementation always yields the IAP api; route the whole
        # batch through Infobip instead when the connector is enabled.
        if SmsApiInfobip._is_enabled(self.env):
            yield SmsApiInfobip(self.env), self
        else:
            yield from super()._split_by_api()
