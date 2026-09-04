from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    credit_alert_warning_percent = fields.Float(
        related='company_id.credit_alert_warning_percent', readonly=False)
    credit_alert_policy = fields.Selection(
        related='company_id.credit_alert_policy', readonly=False)
    credit_alert_notify_user_ids = fields.Many2many(
        related='company_id.credit_alert_notify_user_ids', readonly=False)
    credit_alert_notify_salesperson = fields.Boolean(
        related='company_id.credit_alert_notify_salesperson', readonly=False)
    credit_alert_email_customer = fields.Boolean(
        related='company_id.credit_alert_email_customer', readonly=False)
    credit_alert_customer_template_id = fields.Many2one(
        related='company_id.credit_alert_customer_template_id', readonly=False)
    credit_alert_snooze_days = fields.Integer(
        related='company_id.credit_alert_snooze_days', readonly=False)
