from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    restricted_user_ids = fields.Many2many(
        comodel_name='res.users',
        relation='account_journal_restricted_user_rel',
        column1='journal_id',
        column2='user_id',
        string='Hidden From Users',
        groups='account.group_account_manager',
        domain=lambda self: [
            ('share', '=', False),
            ('groups_id', 'not in', self.env.ref('account.group_account_manager').ids),
        ],
        help="These users cannot see this journal, or any entry, journal item, "
             "payment or bank statement booked in it. "
             "Accounting Administrators always see every journal.",
    )
