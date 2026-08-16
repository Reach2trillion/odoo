# Part of the telegram_notification module. License LGPL-3.
from odoo import models, _
from odoo.tools import html_escape
from odoo.tools.misc import formatLang


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        notifier = self.env['telegram.notifier']
        for move in posted:
            if move.move_type != 'out_invoice':
                continue
            amount = formatLang(self.env, move.amount_total, currency_obj=move.currency_id)
            link = move.get_base_url() + move.get_portal_url()
            body = _("🧾 Your invoice <b>%(name)s</b> (%(amount)s) is available.\n%(link)s") % {
                'name': html_escape(move.name),
                'amount': html_escape(amount),
                'link': link,
            }
            notifier._notify_partner(move.partner_id, body, 'invoice')
        return posted
