from odoo import api, models


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    @api.model_create_multi
    def create(self, vals_list):
        payments = super().create(vals_list)
        payments._aba_khqr_link_requests()
        return payments

    def _aba_khqr_link_requests(self):
        """Attach each KHQR request to the POS payment that used it (via transaction_id)."""
        khqr_payments = self.filtered(
            lambda p: p.transaction_id and p.payment_method_id.use_payment_terminal == 'aba_khqr')
        if not khqr_payments:
            return
        requests = self.env['pos.aba.khqr.request'].sudo().search(
            [('tran_id', 'in', khqr_payments.mapped('transaction_id'))])
        by_tran_id = {request.tran_id: request for request in requests}
        for payment in khqr_payments:
            request = by_tran_id.get(payment.transaction_id)
            if request and not request.pos_payment_id:
                request.write({
                    'pos_payment_id': payment.id,
                    'pos_order_id': payment.pos_order_id.id,
                })
