from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestJournalAccess(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.company_data['company']
        user_values = {
            'groups': 'account.group_account_user,analytic.group_analytic_accounting',
            'company_id': company.id,
            'company_ids': [Command.set(company.ids)],
        }
        cls.restricted_user = new_test_user(cls.env, login='restricted_bookkeeper', **user_values)
        cls.other_user = new_test_user(cls.env, login='other_bookkeeper', **user_values)

        cls.visible_journal = cls.company_data['default_journal_bank']
        cls.hidden_journal = cls.env['account.journal'].create({
            'name': 'ABA of Capital',
            'code': 'CAP',
            'type': 'bank',
            'company_id': company.id,
            'restricted_user_ids': [Command.set(cls.restricted_user.ids)],
        })

        # Bank statement + statement line in each journal.
        cls.hidden_st_line, cls.visible_st_line = cls.env['account.bank.statement.line'].create([
            {'journal_id': journal.id, 'date': fields.Date.today(), 'payment_ref': 'capital', 'amount': 1000.0}
            for journal in (cls.hidden_journal, cls.visible_journal)
        ])
        cls.hidden_statement = cls.env['account.bank.statement'].create({
            'name': 'Hidden statement',
            'line_ids': [Command.set(cls.hidden_st_line.ids)],
        })

        # Customer invoice (visible journal) paid through the hidden journal.
        cls.invoice = cls.init_invoice('out_invoice', amounts=[100.0], post=True)
        cls.hidden_payment = cls.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=cls.invoice.ids,
        ).create({'journal_id': cls.hidden_journal.id})._create_payments()

        # Expense entry in the hidden journal with analytic items.
        cls.analytic_account = cls.env['account.analytic.account'].create({
            'name': 'Office',
            'plan_id': cls.env['account.analytic.plan'].create({'name': 'Departments'}).id,
        })
        cls.hidden_entry = cls.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': cls.hidden_journal.id,
            'date': fields.Date.today(),
            'line_ids': [
                Command.create({
                    'account_id': cls.company_data['default_account_expense'].id,
                    'debit': 50.0,
                    'analytic_distribution': {cls.analytic_account.id: 100},
                }),
                Command.create({
                    'account_id': cls.hidden_journal.default_account_id.id,
                    'credit': 50.0,
                }),
            ],
        })
        cls.hidden_entry.action_post()

    def _search_as(self, user, model, domain):
        return self.env[model].with_user(user).search(domain)

    def test_restricted_user_cannot_see_journal_or_its_records(self):
        user = self.restricted_user
        visible_journals = self._search_as(user, 'account.journal', [])
        self.assertIn(self.visible_journal, visible_journals)
        self.assertNotIn(self.hidden_journal, visible_journals)

        journal_domain = [('journal_id', '=', self.hidden_journal.id)]
        for model in (
            'account.move',
            'account.move.line',
            'account.payment',
            'account.bank.statement',
            'account.bank.statement.line',
            'account.analytic.line',
        ):
            with self.subTest(model=model):
                self.assertFalse(self._search_as(user, model, journal_domain))

        self.assertEqual(self._search_as(user, 'account.bank.statement.line', []), self.visible_st_line)

        for record in (self.hidden_journal, self.hidden_entry, self.hidden_payment, self.hidden_st_line):
            with self.subTest(record=record), self.assertRaises(AccessError):
                record.with_user(user).read(['display_name'])

    def test_restricted_user_totals_exclude_hidden_journal(self):
        domain = [('account_id', '=', self.hidden_journal.default_account_id.id), ('parent_state', '=', 'posted')]
        restricted, = self.env['account.move.line'].with_user(self.restricted_user)._read_group(domain, aggregates=['balance:sum'])
        other, = self.env['account.move.line'].with_user(self.other_user)._read_group(domain, aggregates=['balance:sum'])
        self.assertEqual(restricted[0], 0.0)
        self.assertNotEqual(other[0], 0.0)

    def test_other_users_are_not_affected(self):
        user = self.other_user
        self.assertIn(self.hidden_journal, self._search_as(user, 'account.journal', []))
        journal_domain = [('journal_id', '=', self.hidden_journal.id)]
        self.assertIn(self.hidden_entry, self._search_as(user, 'account.move', journal_domain))
        self.assertEqual(self._search_as(user, 'account.payment', journal_domain), self.hidden_payment)
        self.assertEqual(self._search_as(user, 'account.bank.statement', journal_domain), self.hidden_statement)
        self.assertTrue(self._search_as(user, 'account.analytic.line', journal_domain))

    def test_restricted_user_cannot_post_into_hidden_journal(self):
        with self.assertRaises(AccessError):
            self.env['account.move'].with_user(self.restricted_user).create({
                'move_type': 'entry',
                'journal_id': self.hidden_journal.id,
            })

    def test_invoice_paid_from_hidden_journal_still_opens(self):
        invoice = self.invoice.with_user(self.restricted_user)
        invoice.invalidate_recordset()
        self.assertEqual(invoice.payment_state, self.invoice.payment_state)
        self.assertTrue(invoice.invoice_payments_widget)

    def test_accounting_admin_always_sees_every_journal(self):
        admin = new_test_user(self.env, login='accounting_admin', groups='account.group_account_manager')
        self.hidden_journal.restricted_user_ids |= admin
        self.assertIn(self.hidden_journal, self._search_as(admin, 'account.journal', []))
        self.assertIn(self.hidden_entry, self._search_as(admin, 'account.move', []))

        # ... and the field does not offer them.
        field = self.env['account.journal']._fields['restricted_user_ids']
        selectable = self.env['res.users'].search(field.get_domain_list(self.env['account.journal']))
        self.assertIn(self.restricted_user, selectable)
        self.assertNotIn(admin, selectable)

    def test_restricted_user_cannot_read_restriction_list(self):
        with self.assertRaises(AccessError):
            self.visible_journal.with_user(self.restricted_user).read(['restricted_user_ids'])
