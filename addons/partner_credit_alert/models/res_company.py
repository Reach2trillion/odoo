from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    credit_alert_warning_percent = fields.Float(
        string='Credit Warning Threshold (%)',
        default=80.0,
        help="Raise an 'Approaching Limit' alert once the customer's exposure "
             "(receivable + confirmed but uninvoiced orders) reaches this percentage "
             "of the credit limit. Set 0 to disable the early warning.",
    )
    credit_alert_policy = fields.Selection(
        selection=[
            ('warn', 'Warn only'),
            ('block', 'Block sales orders and customer invoices'),
        ],
        string='Over-Limit Policy',
        default='warn',
        required=True,
        help="What happens when a customer would exceed the credit limit.\n"
             "Warn only: alerts and banners, documents can still be confirmed.\n"
             "Block: confirming a sales order or posting a customer invoice that pushes the "
             "customer over the limit is refused, unless a Credit Manager overrides it.",
    )
    credit_alert_notify_user_ids = fields.Many2many(
        comodel_name='res.users',
        relation='credit_alert_company_notify_user_rel',
        column1='company_id',
        column2='user_id',
        string='Credit Controllers',
        help="Users notified (chatter + activity) whenever a credit alert is raised or escalated.",
    )
    credit_alert_notify_salesperson = fields.Boolean(
        string='Notify Salesperson',
        default=True,
        help="Also notify the salesperson set on the customer.",
    )
    credit_alert_email_customer = fields.Boolean(
        string='E-mail the Customer',
        default=False,
        help="Send an e-mail to the customer when the credit limit is exceeded.",
    )
    credit_alert_customer_template_id = fields.Many2one(
        comodel_name='mail.template',
        string='Customer E-mail Template',
        domain=[('model', '=', 'credit.alert')],
    )
    credit_alert_snooze_days = fields.Integer(
        string='Snooze Days After Manual Resolution',
        default=7,
        help="When an alert is resolved manually while the customer is still over the "
             "threshold, no new alert of the same level is raised for this many days.",
    )
