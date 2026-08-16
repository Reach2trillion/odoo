# Part of the telegram_notification module. License LGPL-3.
from odoo import models, _
from odoo.tools import html_escape
from odoo.tools.misc import formatLang


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def write(self, vals):
        # catch every draft -> sent transition: "Mark as sent" as well as the
        # send-by-email wizard, which writes the state directly
        newly_sent = self.filtered(lambda o: o.state == 'draft') \
            if vals.get('state') == 'sent' else self.browse()
        res = super().write(vals)
        if newly_sent:
            newly_sent._telegram_notify('quotation')
        return res

    def action_confirm(self):
        res = super().action_confirm()
        self._telegram_notify('order')
        return res

    def _telegram_notify(self, event):
        notifier = self.env['telegram.notifier']
        for order in self:
            amount = formatLang(self.env, order.amount_total, currency_obj=order.currency_id)
            link = order.get_base_url() + order.get_portal_url()
            if event == 'quotation':
                body = _("📄 Your quotation <b>%(name)s</b> (%(amount)s) is ready.\n%(link)s")
            else:
                body = _("✅ Your order <b>%(name)s</b> (%(amount)s) is confirmed. Thank you!\n%(link)s")
            notifier._notify_partner(order.partner_id, body % {
                'name': html_escape(order.name),
                'amount': html_escape(amount),
                'link': link,
            }, event)
