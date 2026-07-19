# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    l10n_kh_tax_reportable = fields.Boolean(
        string="Report to GDT (Cambodia)",
        default=True,
        help="If enabled, journal items posted on this account are included "
             "in the Cambodia Monthly Tax Declaration (turnover for the 1% "
             "Prepayment of Tax on Income) and in the e-Filing export.\n"
             "Untick it for accounts whose movements must not be reported "
             "to the General Department of Taxation.",
    )
