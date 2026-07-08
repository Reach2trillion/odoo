# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Khmer PDF Diagnostic",
    'version': '18.0.1.0.0',
    'category': 'Technical',
    'summary': "Minimal test report to isolate a Khmer PDF rendering issue",
    'description': """
Khmer PDF Diagnostic
=====================
A single, bare-bones report with NO custom CSS, NO custom paper
format, and NO Python report parser - just literal Khmer text inside
a standard QWeb template using Odoo's default web.html_container.

Print it from any Contact (Print > Khmer Test) to see whether plain
Khmer text renders correctly in a PDF on this server, with every
other variable (fonts, paperformat, layout) removed from the
equation. Uninstall once the diagnosis is done - this module has no
other purpose.
""",
    'author': 'MRDIL ODOO',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'report/khmer_test_templates.xml',
        'report/khmer_test_actions.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
