# Part of the telegram_notification module. License LGPL-3.
from odoo import models, _
from odoo.tools import html_escape


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _action_done(self):
        res = super()._action_done()
        notifier = self.env['telegram.notifier']
        for picking in self:
            if picking.picking_type_code != 'outgoing' or picking.state != 'done':
                continue
            partner = picking.partner_id or (picking.sale_id and picking.sale_id.partner_id)
            if not partner:
                continue
            parts = [_("📦 Your order <b>%s</b> has been shipped!")
                     % html_escape(picking.sale_id.name or picking.origin or picking.name)]
            if picking.carrier_tracking_ref:
                carrier_name = picking.carrier_id.name or _("Carrier")
                parts.append(_("%(carrier)s tracking reference: <b>%(ref)s</b>") % {
                    'carrier': html_escape(carrier_name),
                    'ref': html_escape(picking.carrier_tracking_ref),
                })
                tracking_url = False
                if picking.carrier_id and hasattr(picking.carrier_id, 'get_tracking_link'):
                    try:
                        tracking_url = picking.carrier_id.get_tracking_link(picking)
                    except Exception:
                        tracking_url = False
                if tracking_url:
                    parts.append(_("Track your package: %s") % tracking_url)
            notifier._notify_partner(partner, '\n'.join(parts), 'delivery')
        return res
