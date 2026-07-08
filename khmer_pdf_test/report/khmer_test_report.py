# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class KhmerTestReport(models.AbstractModel):
    _name = 'report.khmer_pdf_test.report_khmer_test_document'
    _description = "Khmer PDF Diagnostic Report"

    def _get_report_values(self, docids, data=None):
        docs = self.env['res.partner'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'res.partner',
            'docs': docs,
            'python_khmer': "សូមអរគុណសម្រាប់ការទិញឥវ៉ាន់របស់អ្នក!",
        }
