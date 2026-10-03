from odoo import api, fields, models


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    kh_receipt_label = fields.Char(
        string='Receipt label',
        help='Name printed on the customer receipt, e.g. "ABA KHQR". Empty: cash methods print '
             '"សាច់ប្រាក់ / Cash", customer-account methods "គណនីអតិថិជន / Customer Account", '
             'others their name.')

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        return fields_list + ['kh_receipt_label'] if fields_list else fields_list

    def _is_write_forbidden(self, fields):
        # the receipt label is cosmetic: it may change while a session is open (the POS picks it
        # up on its next reload), like the core-whitelisted 'sequence'
        return super()._is_write_forbidden(set(fields) - {'kh_receipt_label'})
