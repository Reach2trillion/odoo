# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from odoo import http
from odoo.http import request

AUTO_PRINT_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>%(title)s</title>
</head>
<body style="margin:0;">
<iframe id="autoprint_frame" title="%(title)s"
        src="data:application/pdf;base64,%(pdf_b64)s"
        style="position:fixed;top:0;left:0;width:100%%;height:100%%;border:0;"></iframe>
<script>
  var frame = document.getElementById('autoprint_frame');
  frame.onload = function () {
    setTimeout(function () {
      try {
        frame.contentWindow.focus();
        frame.contentWindow.print();
      } catch (e) {
        try { window.print(); } catch (e2) { /* printing not available */ }
      }
    }, 400);
  };
</script>
</body>
</html>
"""


class SaleAutoPrintController(http.Controller):

    @http.route('/sale_auto_print/print/<int:attachment_id>', type='http', auth='user')
    def auto_print(self, attachment_id, **kwargs):
        attachment = request.env['ir.attachment'].browse(attachment_id).exists()
        if not attachment or attachment.res_model != 'sale.order':
            return request.not_found()

        pdf_b64 = base64.b64encode(attachment.raw).decode()
        html = AUTO_PRINT_HTML % {
            'title': attachment.name,
            'pdf_b64': pdf_b64,
        }
        return request.make_response(html, headers=[('Content-Type', 'text/html')])
