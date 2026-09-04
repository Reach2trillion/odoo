from odoo import _, api, fields, models
from odoo.tools.misc import formatLang

from .res_partner import CREDIT_ALERT_STATES


class AccountMove(models.Model):
    _inherit = 'account.move'

    credit_alert_state = fields.Selection(
        selection=CREDIT_ALERT_STATES, string='Credit Status',
        compute='_compute_credit_alert_info')
    credit_alert_message = fields.Text(compute='_compute_credit_alert_info')
    credit_alert_blocking = fields.Boolean(
        string='Posting Blocked by Credit Policy', compute='_compute_credit_alert_info')
    credit_alert_override = fields.Boolean(
        string='Credit Override', copy=False, tracking=True,
        groups='partner_credit_alert.group_credit_alert_manager',
        help="Allow posting this invoice even though the customer is over the credit limit "
             "or on hold. The override is logged in the chatter.")
    credit_alert_override_reason = fields.Char(
        string='Override Reason', copy=False, tracking=True,
        groups='partner_credit_alert.group_credit_alert_manager')

    def _credit_alert_applies(self):
        """Customer invoices / receipts in draft are subject to the credit policy."""
        self.ensure_one()
        return self.move_type in ('out_invoice', 'out_receipt') and self.state == 'draft' and (
            self.company_id.account_use_credit_limit
            or self.partner_id.commercial_partner_id.sudo().credit_hold)

    def _credit_alert_document_amount(self):
        self.ensure_one()
        return abs(self.amount_total_signed)

    @api.depends('partner_id', 'company_id', 'amount_total', 'state', 'move_type')
    def _compute_credit_alert_info(self):
        for move in self:
            move = move.with_company(move.company_id)
            move.credit_alert_state = 'no_limit'
            move.credit_alert_message = ''
            move.credit_alert_blocking = False
            if not move.partner_id or not move._credit_alert_applies():
                continue
            partner = move.partner_id.commercial_partner_id
            extra = move._credit_alert_document_amount()
            exclude = move._get_partner_credit_warning_exclude_amount()
            blocked, info = partner._credit_alert_is_blocked(extra_amount=extra, exclude_amount=exclude)
            move.credit_alert_state = info['state']
            if info['state'] in ('warning', 'exceeded', 'hold'):
                move.credit_alert_message = move._credit_alert_build_message(info)
                move.credit_alert_blocking = blocked

    def _credit_alert_build_message(self, info):
        self.ensure_one()
        currency = self.company_id.currency_id
        fmt = lambda amount: formatLang(self.env, amount, currency_obj=currency)  # noqa: E731
        partner = self.partner_id.commercial_partner_id
        if info['state'] == 'hold':
            msg = _("%s is on credit hold: new customer invoices are blocked.", partner.name)
            reason = partner.sudo().credit_hold_reason
            return msg + (_(" Reason: %s", reason) if reason else '')
        if info['state'] == 'exceeded':
            msg = _(
                "%(partner)s exceeds its credit limit of %(limit)s with this invoice: exposure %(exposure)s "
                "(%(percent)s%%).",
                partner=partner.name, limit=fmt(info['limit']), exposure=fmt(info['exposure']),
                percent=f"{info['percent']:.0f}")
            if info['policy'] == 'block':
                msg += " " + _("Posting is blocked by the credit policy.")
            return msg
        return _(
            "%(partner)s is approaching its credit limit of %(limit)s: exposure %(exposure)s "
            "(%(percent)s%%) including this invoice.",
            partner=partner.name, limit=fmt(info['limit']), exposure=fmt(info['exposure']),
            percent=f"{info['percent']:.0f}")

    def _credit_alert_receivable_partners(self):
        """Commercial partners whose receivable balance is affected by these moves."""
        lines = self.line_ids.filtered(
            lambda l: l.partner_id and l.account_id.account_type == 'asset_receivable')
        return lines.partner_id.commercial_partner_id

    def _credit_alert_trigger(self):
        self.ensure_one()
        if self.move_type in ('out_invoice', 'out_receipt'):
            return 'invoice'
        if self.move_type == 'out_refund':
            return 'refund'
        return 'payment'

    def _credit_alert_recheck(self):
        """Re-evaluate every customer touched by these moves, per company."""
        for company, moves in self.grouped('company_id').items():
            for move in moves:
                partners = move._credit_alert_receivable_partners()
                if partners:
                    partners.with_company(company)._credit_alert_check(
                        trigger=move._credit_alert_trigger(), source=move)

    def _post(self, soft=True):
        for move in self:
            move = move.with_company(move.company_id)
            if move.partner_id and move._credit_alert_applies():
                move.partner_id.commercial_partner_id._credit_alert_enforce(
                    move, move._credit_alert_document_amount(),
                    exclude_amount=move._get_partner_credit_warning_exclude_amount())
        posted = super()._post(soft=soft)
        posted._credit_alert_recheck()
        return posted

    def button_draft(self):
        res = super().button_draft()
        # Un-posting an invoice or a payment changes the receivable balance.
        self._credit_alert_recheck()
        return res
