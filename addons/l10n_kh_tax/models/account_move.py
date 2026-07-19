# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_kh_exclude_tax_report = fields.Boolean(
        string="Exclude from Cambodia Tax Report",
        copy=False,
        help="If enabled, this journal entry (invoice, bill or payment) is "
             "not included in the Cambodia Monthly Tax Declaration nor in "
             "the GDT e-Filing export.",
    )
