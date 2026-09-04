from odoo import _, api, fields, models
from odoo.tools.misc import formatLang

from .res_partner import CREDIT_ALERT_STATES


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    credit_alert_state = fields.Selection(
        selection=CREDIT_ALERT_STATES, string='Credit Status',
        compute='_compute_credit_alert_info')
    credit_alert_message = fields.Text(compute='_compute_credit_alert_info')
    credit_alert_blocking = fields.Boolean(
        string='Confirmation Blocked by Credit Policy', compute='_compute_credit_alert_info')
    credit_alert_override = fields.Boolean(
        string='Credit Override', copy=False, tracking=True,
        groups='partner_credit_alert.group_credit_alert_manager',
        help="Allow confirming this order even though the customer is over the credit limit "
             "or on hold. The override is logged in the chatter.")
    credit_alert_override_reason = fields.Char(
        string='Override Reason', copy=False, tracking=True,
        groups='partner_credit_alert.group_credit_alert_manager')

    def _credit_alert_document_amount(self):
        """Order total expressed in company currency."""
        self.ensure_one()
        return self.currency_id._convert(
            self.amount_total, self.company_id.currency_id, self.company_id,
            self.date_order or fields.Date.context_today(self))

    @api.depends('partner_id', 'company_id', 'amount_total', 'state')
    def _compute_credit_alert_info(self):
        for order in self:
            order = order.with_company(order.company_id)
            order.credit_alert_state = 'no_limit'
            order.credit_alert_message = ''
            order.credit_alert_blocking = False
            partner = order.partner_id.commercial_partner_id
            if not partner or not order.company_id.account_use_credit_limit and not partner.sudo().credit_hold:
                continue
            # Draft orders are not in the exposure yet: project them.
            extra = order._credit_alert_document_amount() if order.state in ('draft', 'sent') else 0.0
            blocked, info = partner._credit_alert_is_blocked(extra_amount=extra)
            order.credit_alert_state = info['state']
            if info['state'] in ('warning', 'exceeded', 'hold'):
                order.credit_alert_message = order._credit_alert_build_message(info, extra)
                order.credit_alert_blocking = blocked and order.state in ('draft', 'sent')

    def _credit_alert_build_message(self, info, extra):
        self.ensure_one()
        currency = self.company_id.currency_id
        fmt = lambda amount: formatLang(self.env, amount, currency_obj=currency)  # noqa: E731
        partner = self.partner_id.commercial_partner_id
        if info['state'] == 'hold':
            msg = _("%s is on credit hold: new orders are blocked.", partner.name)
            reason = partner.sudo().credit_hold_reason
            return msg + (_(" Reason: %s", reason) if reason else '')
        if info['state'] == 'exceeded':
            msg = _(
                "%(partner)s exceeds its credit limit of %(limit)s with this order: exposure %(exposure)s "
                "(%(percent)s%%).",
                partner=partner.name, limit=fmt(info['limit']), exposure=fmt(info['exposure']),
                percent=f"{info['percent']:.0f}")
            if info['policy'] == 'block':
                msg += " " + _("Confirmation is blocked by the credit policy.")
            return msg
        return _(
            "%(partner)s is approaching its credit limit of %(limit)s: exposure %(exposure)s "
            "(%(percent)s%%) including this order.",
            partner=partner.name, limit=fmt(info['limit']), exposure=fmt(info['exposure']),
            percent=f"{info['percent']:.0f}")

    def action_confirm(self):
        # Enforce the credit policy before anything is confirmed.
        for order in self:
            order = order.with_company(order.company_id)
            if order.state not in ('draft', 'sent'):
                continue
            partner = order.partner_id.commercial_partner_id
            if not order.company_id.account_use_credit_limit and not partner.sudo().credit_hold:
                continue
            partner._credit_alert_enforce(order, order._credit_alert_document_amount())
        res = super().action_confirm()
        # Now the orders are part of the exposure: raise / escalate alerts.
        for company, orders in self.filtered(lambda o: o.state == 'sale').grouped('company_id').items():
            if not company.account_use_credit_limit:
                continue
            for order in orders:
                order.partner_id.commercial_partner_id.with_company(company)._credit_alert_check(
                    trigger='sale_order', source=order)
        return res
