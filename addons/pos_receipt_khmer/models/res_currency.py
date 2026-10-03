from odoo import api, models
from odoo.osv import expression


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    @api.model
    def _load_pos_data_domain(self, data):
        # also load the riel (KHR) so the receipt can use its rate when the company has no
        # accounting exchange rate (l10n_kh_exchange_rate)
        return expression.OR([super()._load_pos_data_domain(data), [('name', '=', 'KHR')]])
