# Part of the telegram_notification module. License LGPL-3.
from odoo import api, fields, models

from .telegram_notifier import NOTIFICATION_EVENTS


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    telegram_notify_quotation = fields.Boolean(string="Quotation Sent", default=True)
    telegram_notify_order = fields.Boolean(string="Order Confirmed", default=True)
    telegram_notify_delivery = fields.Boolean(string="Delivery Shipped", default=True)
    telegram_notify_invoice = fields.Boolean(string="Invoice Posted", default=True)

    # stored as explicit '1'/'0' (not config_parameter=) because unchecked
    # booleans would otherwise delete the parameter, which is indistinguishable
    # from "never configured" and would re-enable the notification
    def set_values(self):
        super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        for event in NOTIFICATION_EVENTS:
            ICP.set_param('telegram_notification.%s' % event,
                          '1' if self['telegram_notify_%s' % event] else '0')

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        for event in NOTIFICATION_EVENTS:
            res['telegram_notify_%s' % event] = \
                ICP.get_param('telegram_notification.%s' % event, '1') != '0'
        return res
