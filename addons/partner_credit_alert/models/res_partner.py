from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare
from odoo.tools.misc import formatLang

from .credit_alert import LEVEL_RANK

CREDIT_ALERT_STATES = [
    ('no_limit', 'No Credit Limit'),
    ('ok', 'Within Limit'),
    ('warning', 'Approaching Limit'),
    ('exceeded', 'Limit Exceeded'),
    ('hold', 'On Credit Hold'),
]
ALERT_LEVELS = ('warning', 'exceeded')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    credit_alert_policy = fields.Selection(
        selection=[
            ('company', 'Company Default'),
            ('warn', 'Warn only'),
            ('block', 'Block sales orders and customer invoices'),
        ],
        string='Over-Limit Policy', default='company', required=True, tracking=True,
        help="Behaviour when this customer would exceed the credit limit. "
             "'Company Default' uses the policy set in Invoicing > Settings.",
    )
    credit_alert_warning_percent = fields.Float(
        string='Warning Threshold (%)',
        help="Percentage of the credit limit at which an 'Approaching Limit' alert is raised. "
             "Leave 0 to use the company default.",
    )
    credit_hold = fields.Boolean(
        string='Credit Hold', tracking=True, copy=False,
        help="Block new sales orders and customer invoices for this customer regardless of the "
             "balance. Only Credit Managers can set or release a hold.",
    )
    credit_hold_reason = fields.Char(string='Hold Reason', tracking=True, copy=False)

    credit_exposure = fields.Monetary(
        string='Credit Exposure', compute='_compute_credit_alert_status',
        help="Total receivable + confirmed sales orders not yet invoiced.")
    credit_available = fields.Monetary(
        string='Available Credit', compute='_compute_credit_alert_status')
    credit_usage_percent = fields.Float(
        string='Credit Used (%)', compute='_compute_credit_alert_status', digits=(16, 1))
    credit_alert_state = fields.Selection(
        selection=CREDIT_ALERT_STATES, string='Credit Status',
        compute='_compute_credit_alert_status', search='_search_credit_alert_state')
    credit_alert_is_manager = fields.Boolean(compute='_compute_credit_alert_is_manager')

    credit_alert_ids = fields.One2many('credit.alert', 'partner_id', string='Credit Alerts')
    credit_alert_count = fields.Integer(string='Open Credit Alerts', compute='_compute_credit_alert_count')

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends_context('uid')
    def _compute_credit_alert_is_manager(self):
        is_manager = self.env.user.has_group('partner_credit_alert.group_credit_alert_manager')
        for partner in self:
            partner.credit_alert_is_manager = is_manager

    @api.depends_context('company')
    @api.depends('credit_limit', 'credit_hold', 'credit_alert_warning_percent', 'credit_alert_policy')
    def _compute_credit_alert_status(self):
        self._credit_alert_refresh()
        for partner in self:
            info = partner._credit_alert_evaluate(refresh=False)
            partner.credit_exposure = info['exposure']
            partner.credit_available = info['available']
            partner.credit_usage_percent = info['percent']
            partner.credit_alert_state = info['state']

    def _search_credit_alert_state(self, operator, value):
        if operator not in ('=', '!=', 'in', 'not in'):
            raise NotImplementedError(_("Unsupported operator %s on Credit Status", operator))
        values = set(value if isinstance(value, (list, tuple)) else [value])
        all_states = {s[0] for s in CREDIT_ALERT_STATES}
        if operator in ('!=', 'not in'):
            values = all_states - values
        # Only partners with a limit or a hold can be in a state other than 'no_limit'.
        candidates = self.sudo().search([
            '|', ('credit_limit', '>', 0), ('credit_hold', '=', True),
            '|', ('is_company', '=', True), ('parent_id', '=', False),
        ])
        candidates._credit_alert_refresh()
        matching_ids = [p.id for p in candidates if p.credit_alert_state in values]
        domain = [('commercial_partner_id', 'in', matching_ids)]
        if 'no_limit' in values:
            domain = ['|', ('commercial_partner_id', 'not in', candidates.ids)] + domain
        return domain

    @api.depends('credit_alert_ids.state')
    def _compute_credit_alert_count(self):
        groups = self.env['credit.alert']._read_group(
            [('partner_id', 'in', self.commercial_partner_id.ids), ('state', '!=', 'resolved')],
            ['partner_id'], ['__count'])
        counts = {partner.id: count for partner, count in groups}
        for partner in self:
            partner.credit_alert_count = counts.get(partner.commercial_partner_id.id, 0)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def write(self, vals):
        if ('credit_hold' in vals or 'credit_hold_reason' in vals) and not self.env.su \
                and not self.env.user.has_group('partner_credit_alert.group_credit_alert_manager'):
            raise AccessError(_("Only Credit Managers can set or release a credit hold."))
        res = super().write(vals)
        trigger_fields = {'credit_limit', 'credit_hold', 'credit_alert_policy', 'credit_alert_warning_percent'}
        if trigger_fields & vals.keys() and not self.env.context.get('credit_alert_skip_check'):
            self.commercial_partner_id._credit_alert_check(trigger='limit_change')
        return res

    # ------------------------------------------------------------------
    # Credit evaluation
    # ------------------------------------------------------------------

    def _credit_alert_get_settings(self):
        """Return (credit_limit, warning_percent, policy) applicable to this
        customer in the current company. Limit is 0 when the feature is off."""
        self.ensure_one()
        partner = self.commercial_partner_id.sudo()
        company = self.env.company
        limit = partner.credit_limit if company.account_use_credit_limit else 0.0
        percent = partner.credit_alert_warning_percent or company.credit_alert_warning_percent
        policy = partner.credit_alert_policy if partner.credit_alert_policy != 'company' else company.credit_alert_policy
        return limit, percent, policy

    def _credit_alert_refresh(self):
        """`credit` and `credit_to_invoice` are non-stored computes without
        dependencies: drop them from the cache so that documents confirmed or
        posted earlier in the same transaction are taken into account."""
        self.commercial_partner_id.sudo().invalidate_recordset(['credit', 'debit', 'credit_to_invoice'])

    def _credit_alert_evaluate(self, extra_amount=0.0, exclude_amount=0.0, refresh=True):
        """Evaluate the credit situation of the customer.

        :param extra_amount: amount (company currency) of a document about to be
            confirmed that is not yet part of the exposure.
        :param exclude_amount: amount (company currency) already counted in the
            uninvoiced orders that the document will replace (see
            account.move._get_partner_credit_warning_exclude_amount).
        :param refresh: re-read the receivable balance from the database (see
            _credit_alert_refresh); pass False when the caller already did.
        :return: dict with limit, credit, credit_to_invoice, exposure, available,
            percent, level ('none'/'ok'/'warning'/'exceeded'), state and policy.
        """
        self.ensure_one()
        if refresh:
            self._credit_alert_refresh()
        partner = self.commercial_partner_id.sudo()
        company = self.env.company
        currency = company.currency_id
        limit, warning_percent, policy = self._credit_alert_get_settings()
        credit = partner.credit or 0.0
        credit_to_invoice = max((partner.credit_to_invoice or 0.0) - exclude_amount, 0.0)
        exposure = credit + credit_to_invoice + extra_amount
        info = {
            'limit': limit,
            'credit': credit,
            'credit_to_invoice': credit_to_invoice,
            'exposure': exposure,
            'available': 0.0,
            'percent': 0.0,
            'level': 'none',
            'state': 'no_limit',
            'policy': policy,
            'hold': partner.credit_hold,
        }
        if currency.compare_amounts(limit, 0.0) > 0:
            info['available'] = limit - exposure
            info['percent'] = exposure / limit * 100.0
            if currency.compare_amounts(exposure, limit) > 0:
                info['level'] = 'exceeded'
            elif warning_percent > 0 and float_compare(info['percent'], warning_percent, precision_digits=2) >= 0:
                info['level'] = 'warning'
            else:
                info['level'] = 'ok'
            info['state'] = info['level']
        if partner.credit_hold:
            info['state'] = 'hold'
        return info

    def _credit_alert_is_blocked(self, extra_amount=0.0, exclude_amount=0.0):
        """Return (blocked, info) for a document adding `extra_amount` to the exposure."""
        info = self._credit_alert_evaluate(extra_amount=extra_amount, exclude_amount=exclude_amount)
        blocked = info['hold'] or (info['policy'] == 'block' and info['level'] == 'exceeded')
        return blocked, info

    def _credit_alert_block_message(self, info, document_amount=0.0):
        self.ensure_one()
        partner = self.commercial_partner_id
        currency = self.env.company.currency_id
        fmt = lambda amount: formatLang(self.env, amount, currency_obj=currency)  # noqa: E731
        if info['hold']:
            msg = _("%(partner)s is on credit hold", partner=partner.name)
            if partner.sudo().credit_hold_reason:
                msg += _(" (%s)", partner.sudo().credit_hold_reason)
            msg += "."
        else:
            msg = _(
                "%(partner)s would exceed its credit limit of %(limit)s: "
                "total exposure would be %(exposure)s (receivable %(credit)s, orders to invoice "
                "%(to_invoice)s, this document %(amount)s).",
                partner=partner.name, limit=fmt(info['limit']), exposure=fmt(info['exposure']),
                credit=fmt(info['credit']), to_invoice=fmt(info['credit_to_invoice']),
                amount=fmt(document_amount),
            )
        return msg + "\n" + _(
            "Collect a payment first, or ask a Credit Manager to tick 'Credit Override' on this document."
        )

    def _credit_alert_enforce(self, document, document_amount, exclude_amount=0.0):
        """Raise if `document` may not be confirmed under the credit policy.

        Returns the evaluation info. Managers bypass the block by ticking the
        override flag on the document; the override is logged in its chatter."""
        self.ensure_one()
        if self.env.context.get('credit_alert_skip_check'):
            return None
        blocked, info = self._credit_alert_is_blocked(extra_amount=document_amount, exclude_amount=exclude_amount)
        if not blocked:
            return info
        # The override fields are restricted to managers: read them as superuser so a
        # salesperson gets the explanatory error below rather than an access error.
        if document.sudo().credit_alert_override:
            if not self.env.user.has_group('partner_credit_alert.group_credit_alert_manager'):
                raise AccessError(_("Only Credit Managers can override a credit block."))
            document.message_post(body=_(
                "Credit block overridden by %(user)s. Reason: %(reason)s",
                user=self.env.user.name,
                reason=document.sudo().credit_alert_override_reason or _("not specified"),
            ))
            return info
        raise UserError(self._credit_alert_block_message(info, document_amount))

    # ------------------------------------------------------------------
    # Alert lifecycle
    # ------------------------------------------------------------------

    def _credit_alert_check(self, trigger='manual', source=None):
        """Re-evaluate the customers and raise / escalate / resolve credit alerts.

        Must be called with the right company in context (``with_company``).
        Returns the alerts that were created or escalated."""
        Alert = self.env['credit.alert'].sudo()
        company = self.env.company
        touched = Alert.browse()
        partners = self.commercial_partner_id.sudo().with_company(company)
        if not partners:
            return touched
        open_alerts = Alert.search([
            ('partner_id', 'in', partners.ids),
            ('company_id', '=', company.id),
            ('state', '!=', 'resolved'),
        ])
        open_by_partner = {a.partner_id.id: a for a in open_alerts}
        partners._credit_alert_refresh()
        for partner in partners:
            info = partner._credit_alert_evaluate(refresh=False)
            level = info['level']
            alert = open_by_partner.get(partner.id)
            if level in ALERT_LEVELS:
                if alert:
                    touched |= alert._credit_alert_update(info, trigger, source)
                elif not partner._credit_alert_is_snoozed(level):
                    touched |= partner._credit_alert_create(info, trigger, source)
            elif alert:
                alert._resolve_auto(info)
        return touched

    def _credit_alert_is_snoozed(self, level):
        self.ensure_one()
        last = self.env['credit.alert'].sudo().search([
            ('partner_id', '=', self.id),
            ('company_id', '=', self.env.company.id),
            ('state', '=', 'resolved'),
            ('resolution', '=', 'manual'),
        ], order='date_resolved desc, id desc', limit=1)
        if not last or not last.snoozed_until:
            return False
        today = fields.Date.context_today(self)
        return last.snoozed_until >= today and LEVEL_RANK[level] <= LEVEL_RANK[last.level]

    def _credit_alert_create(self, info, trigger, source):
        self.ensure_one()
        alert = self.env['credit.alert'].sudo().create({
            'partner_id': self.id,
            'company_id': self.env.company.id,
            'user_id': self.user_id.id,
            'level': info['level'],
            'trigger': trigger,
            'source_ref': f"{source._name},{source.id}" if source else False,
            'credit_limit': info['limit'],
            'receivable_amount': info['credit'],
            'uninvoiced_amount': info['credit_to_invoice'],
            'exposure': info['exposure'],
            'usage_percent': info['percent'],
            'date_last_check': fields.Datetime.now(),
        })
        alert._notify()
        return alert

    # ------------------------------------------------------------------
    # Cron / manual
    # ------------------------------------------------------------------

    @api.model
    def _cron_credit_alert_check(self):
        """Daily safety net: re-evaluate every customer with a credit limit (or an
        open alert) in every company using credit limits."""
        for company in self.env['res.company'].search([]):
            self_c = self.with_company(company).sudo()
            partners = self_c.browse()
            if company.account_use_credit_limit:
                partners |= self_c.search([
                    ('credit_limit', '>', 0),
                    '|', ('is_company', '=', True), ('parent_id', '=', False),
                ])
            partners |= self_c.env['credit.alert'].search([
                ('company_id', '=', company.id), ('state', '!=', 'resolved'),
            ]).partner_id
            for offset in range(0, len(partners), 500):
                partners[offset:offset + 500]._credit_alert_check(trigger='cron')

    def action_credit_alert_check(self):
        self.commercial_partner_id._credit_alert_check(trigger='manual')
        return True

    def action_view_credit_alerts(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('partner_credit_alert.action_credit_alert')
        action['domain'] = [('partner_id', '=', self.commercial_partner_id.id)]
        action['context'] = {
            'default_partner_id': self.commercial_partner_id.id,
            'search_default_filter_open': 1,
        }
        return action

