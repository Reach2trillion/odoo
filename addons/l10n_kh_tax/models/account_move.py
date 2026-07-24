# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_kh_tax_status = fields.Selection(
        selection=[
            ('default', "Follow Company Default"),
            ('include', "Report to GDT"),
            ('exclude', "Do Not Report"),
        ],
        string="Cambodia Tax Reporting",
        default='default', copy=False, index=True,
        help="Whether this journal entry (invoice, bill or payment) is "
             "included in the Cambodia Monthly Tax Declaration and the GDT "
             "e-Filing export.\n"
             "- Follow Company Default: use the company's Cambodia tax "
             "reporting mode (by default, documents are NOT reported unless "
             "selected).\n"
             "- Report to GDT: always include this document.\n"
             "- Do Not Report: never include this document.")

    def action_l10n_kh_include(self):
        self.write({'l10n_kh_tax_status': 'include'})

    def action_l10n_kh_exclude(self):
        self.write({'l10n_kh_tax_status': 'exclude'})
