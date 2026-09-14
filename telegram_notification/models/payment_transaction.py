# Part of the telegram_notification module. License LGPL-3.
from odoo import models, _
from odoo.tools import html_escape
from odoo.tools.misc import formatLang


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _set_done(self, *args, **kwargs):
        # returns the transactions that actually moved to 'done'
        txs = super()._set_done(*args, **kwargs)
        txs._telegram_notify_payment()
        return txs

    def _telegram_notify_payment(self):
        notifier = self.env['telegram.notifier']
        for tx in self:
            if tx.operation == 'refund' or tx.amount <= 0:
                continue
            amount = formatLang(self.env, tx.amount, currency_obj=tx.currency_id)
            orders = tx.sale_order_ids if 'sale_order_ids' in tx._fields else self.env['sale.order']
            invoices = tx.invoice_ids if 'invoice_ids' in tx._fields else self.env['account.move']
            documents = orders.mapped('name') + invoices.mapped('name')
            docs_text = ' — %s' % ', '.join(documents) if documents else ''

            # confirmation to the customer
            customer_body = _("✅ Payment of <b>%(amount)s</b> received%(docs)s. Thank you!") % {
                'amount': html_escape(amount),
                'docs': html_escape(docs_text),
            }
            if orders:
                customer_body += '\n' + orders[0].get_base_url() + orders[0].get_portal_url()
            notifier._notify_partner(tx.partner_id, customer_body, 'payment')

            # alert to the director / staff
            notifier._notify_staff(tx._telegram_payment_alert_body(amount, orders, invoices), 'payment_alert')

    def _telegram_payment_alert_body(self, amount, orders, invoices):
        self.ensure_one()
        partner = self.partner_id
        contact = [partner.name or _("Unknown customer")]
        if partner.telegram_username:
            contact.append('@%s' % partner.telegram_username)
        phone = partner.phone or partner.mobile or partner.commercial_partner_id.phone
        if phone:
            contact.append(phone)
        lines = [
            _("💰 <b>Payment received: %s</b>") % html_escape(amount),
            _("Customer: %s") % html_escape(' · '.join(contact)),
        ]
        if orders:
            lines.append(_("Order: %s") % html_escape(', '.join(orders.mapped('name'))))
        if invoices:
            lines.append(_("Invoice: %s") % html_escape(', '.join(invoices.mapped('name'))))
        lines.append(_("Via: %(provider)s (ref. %(reference)s)") % {
            'provider': html_escape(self.provider_id.name or ''),
            'reference': html_escape(self.reference or ''),
        })
        base_url = self.get_base_url()
        if orders:
            lines.append('%s/odoo/action-sale.action_orders/%d' % (base_url, orders[0].id))
        else:
            lines.append('%s/odoo/action-payment.action_payment_transaction/%d' % (base_url, self.id))
        return '\n'.join(lines)
