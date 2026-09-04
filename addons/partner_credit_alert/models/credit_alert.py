from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import formatLang

LEVEL_RANK = {'warning': 1, 'exceeded': 2}


class CreditAlert(models.Model):
    _name = 'credit.alert'
    _description = 'Customer Credit Alert'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_detected desc, id desc'
    _rec_name = 'name'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    partner_id = fields.Many2one(
        comodel_name='res.partner', string='Customer', required=True, index=True,
        ondelete='cascade', tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related='company_id.currency_id')
    user_id = fields.Many2one(
        comodel_name='res.users', string='Salesperson', tracking=True,
        help="Salesperson of the customer at the time the alert was raised.",
    )
    level = fields.Selection(
        selection=[('warning', 'Approaching Limit'), ('exceeded', 'Limit Exceeded')],
        string='Level', required=True, tracking=True, index=True,
    )
    state = fields.Selection(
        selection=[('open', 'Open'), ('acknowledged', 'Acknowledged'), ('resolved', 'Resolved')],
        string='Status', default='open', required=True, tracking=True, index=True, copy=False,
    )
    resolution = fields.Selection(
        selection=[('auto', 'Back within limit'), ('manual', 'Resolved manually')],
        string='Resolution', copy=False, readonly=True,
    )
    trigger = fields.Selection(
        selection=[
            ('sale_order', 'Sales Order Confirmed'),
            ('invoice', 'Customer Invoice Posted'),
            ('refund', 'Credit Note Posted'),
            ('payment', 'Payment / Journal Entry'),
            ('limit_change', 'Credit Limit or Policy Changed'),
            ('cron', 'Scheduled Check'),
            ('manual', 'Manual Check'),
        ],
        string='Raised By', required=True, default='manual', readonly=True,
    )
    source_ref = fields.Reference(
        selection=[('sale.order', 'Sales Order'), ('account.move', 'Journal Entry')],
        string='Source Document', readonly=True,
        help="Document whose confirmation triggered this alert, if any.",
    )
    credit_limit = fields.Monetary(string='Credit Limit', readonly=True)
    receivable_amount = fields.Monetary(
        string='Receivable', readonly=True,
        help="Unpaid posted receivable balance (Total Receivable on the customer).")
    uninvoiced_amount = fields.Monetary(
        string='Orders To Invoice', readonly=True,
        help="Confirmed sales orders not invoiced yet.")
    exposure = fields.Monetary(
        string='Total Exposure', readonly=True,
        help="Receivable + confirmed orders to invoice.")
    usage_percent = fields.Float(string='Limit Usage (%)', readonly=True, digits=(16, 1))
    overrun = fields.Monetary(string='Over Limit By', compute='_compute_overrun')
    date_detected = fields.Datetime(string='Raised On', default=fields.Datetime.now, readonly=True, required=True)
    date_last_check = fields.Datetime(string='Last Check', readonly=True)
    date_resolved = fields.Datetime(string='Resolved On', readonly=True, copy=False)
    acknowledged_by_id = fields.Many2one('res.users', string='Acknowledged By', readonly=True, copy=False)
    acknowledged_date = fields.Datetime(string='Acknowledged On', readonly=True, copy=False)
    snoozed_until = fields.Date(
        string='Snoozed Until', copy=False,
        help="After a manual resolution, no new alert of the same (or lower) level is raised "
             "for this customer before this date.",
    )
    note = fields.Html(string='Internal Notes')
    color = fields.Integer(compute='_compute_color')

    @api.depends('exposure', 'credit_limit')
    def _compute_overrun(self):
        for alert in self:
            alert.overrun = max(alert.exposure - alert.credit_limit, 0.0)

    @api.depends('level', 'state')
    def _compute_color(self):
        for alert in self:
            if alert.state == 'resolved':
                alert.color = 10  # green
            elif alert.level == 'exceeded':
                alert.color = 1  # red
            else:
                alert.color = 2  # orange

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].with_company(
                    vals.get('company_id')).next_by_code('credit.alert') or 'New'
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_acknowledge(self):
        for alert in self:
            if alert.state != 'open':
                continue
            alert.write({
                'state': 'acknowledged',
                'acknowledged_by_id': self.env.user.id,
                'acknowledged_date': fields.Datetime.now(),
            })
            alert.activity_feedback(['partner_credit_alert.mail_activity_type_credit_review'])
        return True

    def action_resolve(self):
        """Manual resolution by a user. Snoozes the alert so the next scheduled
        check does not immediately re-open an identical one."""
        for alert in self:
            if alert.state == 'resolved':
                continue
            snooze_days = alert.company_id.credit_alert_snooze_days
            alert.write({
                'state': 'resolved',
                'resolution': 'manual',
                'date_resolved': fields.Datetime.now(),
                'snoozed_until': alert.snoozed_until or (
                    fields.Date.context_today(alert) + timedelta(days=snooze_days)
                    if snooze_days > 0 else False),
            })
            alert.activity_unlink(['partner_credit_alert.mail_activity_type_credit_review'])
            alert.message_post(body=_("Resolved manually by %s.", self.env.user.name))
        return True

    def action_reopen(self):
        for alert in self:
            if alert.state != 'resolved':
                continue
            alert.write({
                'state': 'open', 'resolution': False, 'date_resolved': False, 'snoozed_until': False,
            })
        return True

    def action_recheck(self):
        """Re-evaluate the customer right now (e.g. after a payment was registered)."""
        for alert in self:
            alert.partner_id.with_company(alert.company_id)._credit_alert_check(trigger='manual')
        return True

    def action_open_partner(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_source(self):
        self.ensure_one()
        if not self.source_ref:
            raise UserError(_("This alert is not linked to a document."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.source_ref._name,
            'res_id': self.source_ref.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ------------------------------------------------------------------
    # Refresh / escalation (called from res.partner._credit_alert_check)
    # ------------------------------------------------------------------

    def _credit_alert_update(self, info, trigger, source):
        """Refresh an open alert with the latest figures; escalate or de-escalate
        the level if needed. Returns the alert if it was escalated."""
        self.ensure_one()
        vals = {
            'receivable_amount': info['credit'],
            'uninvoiced_amount': info['credit_to_invoice'],
            'exposure': info['exposure'],
            'usage_percent': info['percent'],
            'date_last_check': fields.Datetime.now(),
        }
        escalated = LEVEL_RANK[info['level']] > LEVEL_RANK[self.level]
        lowered = LEVEL_RANK[info['level']] < LEVEL_RANK[self.level]
        if escalated or lowered:
            vals['level'] = info['level']
            vals['trigger'] = trigger
            if source:
                vals['source_ref'] = f"{source._name},{source.id}"
            if escalated and self.state == 'acknowledged':
                vals['state'] = 'open'  # needs a fresh look
        self.write(vals)
        if escalated:
            self._notify(escalated=True)
            return self
        if lowered:
            self.message_post(body=_("Alert level lowered to %s.", dict(
                self._fields['level']._description_selection(self.env))[info['level']]))
        return self.browse()

    # ------------------------------------------------------------------
    # Automatic resolution (called from res.partner._credit_alert_check)
    # ------------------------------------------------------------------

    def _resolve_auto(self, info):
        """The customer is back within the limit: close the alert."""
        now = fields.Datetime.now()
        for alert in self:
            alert.write({
                'state': 'resolved',
                'resolution': 'auto',
                'date_resolved': now,
                'date_last_check': now,
                'receivable_amount': info['credit'],
                'uninvoiced_amount': info['credit_to_invoice'],
                'exposure': info['exposure'],
                'usage_percent': info['percent'],
            })
            alert.activity_unlink(['partner_credit_alert.mail_activity_type_credit_review'])
            alert.message_post(body=_(
                "Customer is back within the credit limit (exposure %(exposure)s of %(limit)s). "
                "Alert resolved automatically.",
                exposure=alert._fmt(info['exposure']),
                limit=alert._fmt(info['limit']),
            ))
            alert.partner_id.message_post(
                body=_("Credit alert %s resolved: customer is back within the credit limit.", alert.name),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def _fmt(self, amount):
        self.ensure_one()
        return formatLang(self.env, amount, currency_obj=self.currency_id)

    def _get_notified_users(self):
        self.ensure_one()
        company = self.company_id
        users = company.credit_alert_notify_user_ids
        if company.credit_alert_notify_salesperson and self.user_id:
            users |= self.user_id
        return users.filtered(lambda u: u.active and not u.share and self._user_can_access(u))

    def _user_can_access(self, user):
        """Activities can only be assigned to users who can read the alert."""
        try:
            self.with_user(user).with_company(self.company_id).check_access('read')
        except AccessError:
            return False
        return True

    def _notify(self, escalated=False):
        """Post the alert in the chatter (notifying credit controllers and the
        salesperson), schedule a review activity for them, log on the customer
        and optionally e-mail the customer."""
        for alert in self:
            users = alert._get_notified_users()
            level_label = dict(alert._fields['level']._description_selection(alert.env))[alert.level]
            title = _("Credit alert escalated to %s", level_label) if escalated else _("Credit alert: %s", level_label)
            body = Markup(
                "<p><b>%(title)s</b> - %(partner)s</p>"
                "<ul>"
                "<li>%(l_limit)s: %(limit)s</li>"
                "<li>%(l_recv)s: %(recv)s</li>"
                "<li>%(l_uninv)s: %(uninv)s</li>"
                "<li>%(l_expo)s: <b>%(expo)s</b> (%(pct)s%% %(l_of_limit)s)</li>"
                "</ul>"
            ) % {
                'title': title,
                'partner': alert.partner_id.display_name,
                'l_limit': _("Credit limit"), 'limit': alert._fmt(alert.credit_limit),
                'l_recv': _("Receivable"), 'recv': alert._fmt(alert.receivable_amount),
                'l_uninv': _("Orders to invoice"), 'uninv': alert._fmt(alert.uninvoiced_amount),
                'l_expo': _("Total exposure"), 'expo': alert._fmt(alert.exposure),
                'pct': f"{alert.usage_percent:.0f}", 'l_of_limit': _("of the limit"),
            }
            if users:
                alert.message_subscribe(partner_ids=users.partner_id.ids)
            alert.message_post(
                body=body,
                subject=title,
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
                partner_ids=users.partner_id.ids,
            )
            alert.partner_id.message_post(
                body=body,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
            # One review activity per notified user (skip if one is already pending).
            pending_users = alert.activity_ids.filtered(
                lambda a: a.activity_type_id == alert.env.ref(
                    'partner_credit_alert.mail_activity_type_credit_review', raise_if_not_found=False)
            ).user_id
            for user in users - pending_users:
                alert.activity_schedule(
                    'partner_credit_alert.mail_activity_type_credit_review',
                    user_id=user.id,
                    summary=_("%(level)s: %(partner)s", level=level_label, partner=alert.partner_id.name),
                    note=body,
                )
            if alert.level == 'exceeded':
                alert._send_customer_email()

    def _send_customer_email(self):
        self.ensure_one()
        company = self.company_id
        template = company.credit_alert_customer_template_id or self.env.ref(
            'partner_credit_alert.email_template_credit_alert_customer', raise_if_not_found=False)
        if not company.credit_alert_email_customer or not template or not self.partner_id.email:
            return
        template.with_context(lang=self.partner_id.lang).send_mail(self.id, force_send=False)
        self.message_post(body=_("Credit limit notification e-mailed to %s.", self.partner_id.email))
