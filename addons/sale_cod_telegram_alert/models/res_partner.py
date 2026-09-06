# -*- coding: utf-8 -*-
from odoo import fields, models

from .common import COD_PAYMENT_TYPES


class ResPartner(models.Model):
    _inherit = 'res.partner'

    cod_payment_type = fields.Selection(
        COD_PAYMENT_TYPES,
        string='Default Delivery Payment',
        help='Pre-fills "Delivery Payment" on new sales orders of this customer, '
             'e.g. "Pay Later / Credit" for shops that settle by bank transfer. '
             'Leave empty to default to Cash on Delivery.',
    )
