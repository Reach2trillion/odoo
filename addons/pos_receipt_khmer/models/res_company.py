from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    kh_name = fields.Char(
        string='Khmer trade name (receipt)',
        help='Khmer shop name printed at the top of the POS receipt. The line is hidden when empty.')
    kh_address_km = fields.Char(
        string='Receipt address (Khmer)',
        help='Khmer address line. Empty: city and province (state) of the company.')
    kh_address_en = fields.Char(
        string='Receipt address (English)',
        help='English address line, e.g. "Ta Khmau, Kandal". Hidden when empty.')
    kh_doc_title = fields.Selection(
        [('invoice', 'វិក្កយបត្រ / INVOICE'), ('receipt', 'បង្កាន់ដៃលក់ / SALES RECEIPT')],
        string='Receipt title', default='invoice', required=True,
        help='Title band and number label printed on a paid POS receipt. Ask your accountant which one applies.')
    kh_tin_label = fields.Selection(
        [('none', 'Do not print'),
         ('tin', 'លេខអត្តសញ្ញាណកម្ម / TIN'),
         ('vattin', 'លេខអត្តសញ្ញាណកម្ម អតប / VATTIN')],
        string='Tax ID label', default='tin', required=True,
        help='How the company Tax ID is printed. Use VATTIN only once the accountant confirms the '
             'VAT registration and the number.')
    kh_receipt_logo = fields.Image(
        string='Receipt logo (thermal, 1-bit, 200 px wide)',
        help='Optional black and white logo for the thermal printer: a 1-bit PNG exactly 200 px wide, '
             'hairlines at least 2 px. Empty: the company logo is used.')
    kh_has_receipt_logo = fields.Boolean(
        string='Has receipt logo', compute='_compute_kh_has_receipt_logo', store=True)

    @api.depends('kh_receipt_logo')
    def _compute_kh_has_receipt_logo(self):
        for company in self:
            company.kh_has_receipt_logo = bool(company.kh_receipt_logo)

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        if not fields_list:
            # [] means "all fields": nothing to add
            return fields_list
        fields_list = fields_list + [
            'kh_name', 'kh_address_km', 'kh_address_en', 'kh_doc_title', 'kh_tin_label', 'kh_has_receipt_logo',
        ]
        # l10n_kh_tax (optional, no hard dependency) provides the accounting exchange rate
        if 'l10n_kh_exchange_rate' in self._fields:
            fields_list.append('l10n_kh_exchange_rate')
        return fields_list
