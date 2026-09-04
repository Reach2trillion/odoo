from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.sale.tests.common import TestSaleCommon


@tagged('post_install', '-at_install')
class TestCreditAlert(TestSaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.company.write({
            'account_use_credit_limit': True,
            'credit_alert_warning_percent': 80.0,
            'credit_alert_policy': 'warn',
            'credit_alert_notify_salesperson': True,
            'credit_alert_email_customer': False,
            'credit_alert_snooze_days': 7,
        })
        cls.Alert = cls.env['credit.alert']
        cls.manager_group = cls.env.ref('partner_credit_alert.group_credit_alert_manager')
        cls.sales_user = cls.env['res.users'].create({
            'name': 'Sally Sales',
            'login': 'sally_credit_alert',
            'email': 'sally@example.com',
            'company_id': cls.company.id,
            'company_ids': [Command.link(cls.company.id)],
            'groups_id': [Command.set([
                cls.env.ref('sales_team.group_sale_salesman').id,
                cls.env.ref('account.group_account_invoice').id,
                cls.env.ref('base.group_partner_manager').id,
            ])],
        })
        cls.manager_user = cls.env['res.users'].create({
            'name': 'Max Manager',
            'login': 'max_credit_alert',
            'email': 'max@example.com',
            'company_id': cls.company.id,
            'company_ids': [Command.link(cls.company.id)],
            'groups_id': [Command.set([
                cls.env.ref('sales_team.group_sale_salesman_all_leads').id,
                cls.env.ref('account.group_account_invoice').id,
                cls.env.ref('base.group_partner_manager').id,
                cls.manager_group.id,
            ])],
        })
        cls.company.credit_alert_notify_user_ids = [Command.set([cls.manager_user.id])]
        cls.customer = cls.partner_a
        cls.customer.write({'user_id': cls.sales_user.id})
        cls.customer.with_company(cls.company).with_context(credit_alert_skip_check=True).credit_limit = 1000.0
        cls.product_a.taxes_id = [Command.clear()]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _order(self, amount, partner=None, user=None):
        env = self.env if user is None else self.env(user=user.id)
        return env['sale.order'].with_company(self.company).create({
            'partner_id': (partner or self.customer).id,
            'order_line': [Command.create({
                'product_id': self.product_a.id,
                'product_uom_qty': 1.0,
                'price_unit': amount,
                'tax_id': [Command.clear()],
            })],
        })

    def _invoice(self, amount, post=False):
        return self.init_invoice(
            'out_invoice', partner=self.customer, amounts=[amount],
            taxes=self.env['account.tax'], post=post, company=self.company)

    def _payment(self, amount):
        payment = self.env['account.payment'].with_company(self.company).create({
            'amount': amount,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.customer.id,
            'journal_id': self.company_data['default_journal_bank'].id,
        })
        payment.action_post()
        return payment

    def _open_alerts(self):
        return self.Alert.search([('partner_id', '=', self.customer.id), ('state', '!=', 'resolved')])

    def _status(self):
        return self.customer.with_company(self.company).credit_alert_state

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_01_warning_then_escalation(self):
        self.assertEqual(self._status(), 'ok')
        order = self._order(850.0)
        self.assertEqual(order.credit_alert_state, 'warning', "Draft order should project the exposure")
        self.assertIn('approaching', order.credit_alert_message)
        order.action_confirm()

        self.assertEqual(self._status(), 'warning')
        alerts = self._open_alerts()
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert.level, 'warning')
        self.assertEqual(alert.trigger, 'sale_order')
        self.assertEqual(alert.source_ref, order)
        self.assertEqual(alert.user_id, self.sales_user)
        self.assertAlmostEqual(alert.exposure, 850.0)
        self.assertAlmostEqual(alert.usage_percent, 85.0)
        self.assertTrue(alert.name.startswith('CA/'))
        # Salesperson and credit controller get a review activity.
        activity_users = alert.activity_ids.mapped('user_id')
        self.assertIn(self.sales_user, activity_users)
        self.assertIn(self.manager_user, activity_users)
        self.assertIn(self.manager_user.partner_id, alert.message_partner_ids)

        # Second order pushes over the limit: same alert escalates, no duplicate.
        self._order(300.0).action_confirm()
        self.assertEqual(self._status(), 'exceeded')
        alerts = self._open_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts, alert)
        self.assertEqual(alert.level, 'exceeded')
        self.assertAlmostEqual(alert.exposure, 1150.0)
        self.assertAlmostEqual(alert.overrun, 150.0)
        self.assertAlmostEqual(self.customer.with_company(self.company).credit_available, -150.0)

    def test_02_block_policy_on_sale_order(self):
        self.customer.credit_alert_policy = 'block'
        order = self._order(1200.0, user=self.sales_user)
        self.assertEqual(order.credit_alert_state, 'exceeded')
        self.assertTrue(order.credit_alert_blocking)
        with self.assertRaisesRegex(UserError, 'would exceed its credit limit'):
            order.action_confirm()
        self.assertEqual(order.state, 'draft')
        self.assertFalse(self._open_alerts())

        # A salesperson cannot set the override flag (field restricted to managers).
        with self.assertRaises(AccessError):
            order.write({'credit_alert_override': True})
        # ... nor confirm with one set on their behalf.
        order.sudo().write({'credit_alert_override': True, 'credit_alert_override_reason': 'test'})
        with self.assertRaises(AccessError):
            order.action_confirm()

        # A credit manager can override, and the override is logged.
        manager_order = order.with_user(self.manager_user)
        manager_order.action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertTrue(any('overridden' in (m.body or '') for m in order.message_ids))
        alert = self._open_alerts()
        self.assertEqual(alert.level, 'exceeded')

        # Within-limit orders are never blocked.
        self.customer.credit_alert_policy = 'warn'
        self.assertEqual(self._status(), 'exceeded')
        self._order(10.0).action_confirm()  # warn only: passes

    def test_03_company_default_policy(self):
        self.company.credit_alert_policy = 'block'
        self.assertEqual(self.customer.credit_alert_policy, 'company')
        order = self._order(1500.0)
        with self.assertRaises(UserError):
            order.action_confirm()
        self.customer.credit_alert_policy = 'warn'  # partner-level override of the company policy
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_04_credit_hold(self):
        with self.assertRaises(AccessError):
            self.customer.with_user(self.sales_user).write({'credit_hold': True})
        self.customer.with_user(self.manager_user).write({'credit_hold': True, 'credit_hold_reason': 'Disputed invoices'})
        self.assertEqual(self._status(), 'hold')
        order = self._order(10.0)
        self.assertEqual(order.credit_alert_state, 'hold')
        self.assertIn('Disputed invoices', order.credit_alert_message)
        with self.assertRaises(UserError):
            order.action_confirm()
        invoice = self._invoice(10.0)
        self.assertEqual(invoice.credit_alert_state, 'hold')
        with self.assertRaises(UserError):
            invoice.action_post()
        self.assertIn(self.customer, self.env['res.partner'].search([('credit_alert_state', '=', 'hold')]))
        self.customer.with_user(self.manager_user).write({'credit_hold': False})
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_05_invoice_block_and_payment_resolution(self):
        invoice = self._invoice(1200.0)
        self.assertEqual(invoice.credit_alert_state, 'exceeded')
        invoice.action_post()
        alert = self._open_alerts()
        self.assertEqual(len(alert), 1)
        self.assertEqual(alert.level, 'exceeded')
        self.assertEqual(alert.trigger, 'invoice')
        self.assertEqual(alert.source_ref, invoice)
        self.assertAlmostEqual(alert.receivable_amount, 1200.0)

        self.customer.credit_alert_policy = 'block'
        second = self._invoice(50.0)
        self.assertTrue(second.credit_alert_blocking)
        with self.assertRaises(UserError):
            second.action_post()
        self.assertEqual(second.state, 'draft')

        # The customer pays: the alert resolves itself and invoicing is unblocked.
        self._payment(1200.0)
        self.assertEqual(self._status(), 'ok')
        self.assertEqual(alert.state, 'resolved')
        self.assertEqual(alert.resolution, 'auto')
        self.assertTrue(alert.date_resolved)
        self.assertFalse(alert.activity_ids)
        second.action_post()
        self.assertEqual(second.state, 'posted')
        self.assertFalse(self._open_alerts())

    def test_06_reset_to_draft_recheck(self):
        invoice = self._invoice(1200.0, post=True)
        alert = self._open_alerts()
        self.assertEqual(alert.level, 'exceeded')
        invoice.button_draft()
        self.assertEqual(alert.state, 'resolved')
        self.assertEqual(self._status(), 'ok')

    def test_07_limit_change_recheck(self):
        self._order(900.0).action_confirm()
        alert = self._open_alerts()
        self.assertEqual(alert.level, 'warning')
        # Raising the limit resolves the alert; lowering it re-raises one.
        self.customer.with_company(self.company).credit_limit = 5000.0
        self.assertEqual(alert.state, 'resolved')
        self.customer.with_company(self.company).credit_limit = 500.0
        new_alert = self._open_alerts()
        self.assertEqual(len(new_alert), 1)
        self.assertNotEqual(new_alert, alert)
        self.assertEqual(new_alert.level, 'exceeded')
        self.assertEqual(new_alert.trigger, 'limit_change')

    def test_08_manual_resolution_snooze_and_cron(self):
        self._order(900.0).action_confirm()
        alert = self._open_alerts()
        alert.action_acknowledge()
        self.assertEqual(alert.state, 'acknowledged')
        self.assertEqual(alert.acknowledged_by_id, self.env.user)
        alert.action_resolve()
        self.assertEqual(alert.state, 'resolved')
        self.assertEqual(alert.resolution, 'manual')
        self.assertEqual(alert.snoozed_until, fields.Date.context_today(alert) + timedelta(days=7))

        # Still at 90 %, but snoozed: the scheduled check must not re-raise a warning.
        self.env['res.partner']._cron_credit_alert_check()
        self.assertFalse(self._open_alerts())

        # Escalation to a higher level is never snoozed.
        self._order(200.0).action_confirm()
        exceeded = self._open_alerts()
        self.assertEqual(exceeded.level, 'exceeded')
        self.assertNotEqual(exceeded, alert)

        # After the snooze period, the scheduled check raises again.
        exceeded.action_resolve()
        exceeded.snoozed_until = fields.Date.context_today(alert) - timedelta(days=1)
        self.env['res.partner']._cron_credit_alert_check()
        again = self._open_alerts()
        self.assertEqual(len(again), 1)
        self.assertEqual(again.trigger, 'cron')

    def test_09_search_credit_state(self):
        Partner = self.env['res.partner']
        self.assertIn(self.customer, Partner.search([('credit_alert_state', '=', 'ok')]))
        self.assertIn(self.partner_b, Partner.search([('credit_alert_state', '=', 'no_limit')]))
        self._order(1100.0).action_confirm()
        self.assertIn(self.customer, Partner.search([('credit_alert_state', '=', 'exceeded')]))
        self.assertNotIn(self.customer, Partner.search([('credit_alert_state', '!=', 'exceeded')]))
        self.assertIn(self.customer, Partner.search([('credit_alert_state', 'in', ['warning', 'exceeded'])]))

    def test_10_customer_email(self):
        self.company.write({'credit_alert_email_customer': True})
        self.customer.email = 'customer@example.com'
        self._order(1100.0).action_confirm()
        alert = self._open_alerts()
        mail = self.env['mail.mail'].search([('model', '=', 'credit.alert'), ('res_id', '=', alert.id)])
        self.assertEqual(len(mail), 1)
        self.assertIn(self.customer, mail.recipient_ids)
        self.assertIn('credit limit', mail.subject)

    def test_12_no_activity_for_user_without_access(self):
        plain_user = self.env['res.users'].create({
            'name': 'Plain Internal', 'login': 'plain_credit_alert',
            'company_id': self.company.id, 'company_ids': [Command.link(self.company.id)],
            'groups_id': [Command.set([self.env.ref('base.group_user').id])],
        })
        self.customer.user_id = plain_user
        self._order(1100.0).action_confirm()  # must not raise
        alert = self._open_alerts()
        self.assertEqual(len(alert), 1)
        self.assertNotIn(plain_user, alert.activity_ids.user_id)
        self.assertIn(self.manager_user, alert.activity_ids.user_id)

    def test_11_feature_off_when_company_limit_disabled(self):
        self.company.account_use_credit_limit = False
        self.assertEqual(self._status(), 'no_limit')
        self._order(5000.0).action_confirm()
        self.assertFalse(self._open_alerts())
