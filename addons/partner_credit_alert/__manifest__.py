{
    'name': 'Customer Credit Alerts',
    'summary': 'Alert, notify and optionally block when customers approach or exceed their credit limit',
    'description': """
Customer Credit Alerts
======================
Builds on Odoo's native credit limit (Invoicing > Settings > Sales Credit Limit) and adds:

* Two-level alerts: *Approaching Limit* (configurable % of the limit) and *Limit Exceeded*.
* Alert records with their own lifecycle (open / acknowledged / resolved), chatter and activities.
* Automatic notification of the salesperson and a configurable list of credit controllers.
* Optional e-mail to the customer when the limit is exceeded.
* Per-partner or company-wide policy: warn only, or block confirmation of sales orders and
  posting of customer invoices. Credit managers can override a block with a reason.
* Manual *Credit Hold* on a customer that blocks new sales regardless of the balance.
* Live credit status on the customer form (exposure, available credit, usage %), red/orange
  banners on quotations and invoices, smart button to the alerts.
* Alerts are re-evaluated on every event that changes the exposure (order confirmation,
  invoice, refund, payment, entry reset to draft, limit change) and by a daily scheduled check,
  and are resolved automatically once the customer is back within the limit.
""",
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'author': 'Reach2Trillion',
    'website': 'https://github.com/reach2trillion/odoo',
    'license': 'LGPL-3',
    'depends': ['account', 'sale', 'mail'],
    'data': [
        'security/credit_alert_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/mail_activity_type_data.xml',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
        'views/credit_alert_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
