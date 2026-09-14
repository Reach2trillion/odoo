# Part of the telegram_notification module. License LGPL-3.
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    telegram_payment_alerts = fields.Boolean(
        string='Telegram Payment Alerts',
        help="Send this user a Telegram message each time a customer payment "
             "succeeds. The user must be linked to a Telegram account and have "
             "allowed the bot to message them (or pressed Start on the bot).")
