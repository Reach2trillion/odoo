# -*- coding: utf-8 -*-
from odoo import fields, models

from .common import (
    DEFAULT_TRIGGER,
    LABEL_TEXT_DEFAULTS,
    PARAM_BOT_TOKEN,
    PARAM_CHAT_ID,
    PARAM_LABEL_HIDE,
    PARAM_LABEL_TEXT,
    PARAM_ONLY_COD,
    PARAM_SKIP_UPDATE,
    PARAM_TRIGGER,
    TRIGGER_SELECTION,
)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # --- Telegram alert -------------------------------------------------
    cod_alert_chat_id = fields.Char(
        string='COD Alert Telegram Chat ID',
        config_parameter=PARAM_CHAT_ID,
        help='Group or chat that receives the COD / PAID alerts. Leave empty to '
             'reuse the Telegram group of the delivery operation type (Delivery '
             'Packing Telegram Notification module), so the alert lands next to '
             'the packing message.',
    )
    cod_alert_bot_token = fields.Char(
        string='Telegram Bot Token',
        config_parameter=PARAM_BOT_TOKEN,
        help='Optional. Leave empty to reuse the bot configured in the '
             '"Send by Telegram" settings.',
    )
    cod_alert_trigger = fields.Selection(
        TRIGGER_SELECTION,
        string='Send the alert',
        default=DEFAULT_TRIGGER,
        required=True,
        config_parameter=PARAM_TRIGGER,
    )
    cod_alert_only_cod = fields.Boolean(
        string='Only alert Cash on Delivery orders',
        config_parameter=PARAM_ONLY_COD,
        help='By default every delivery is announced (COD, PAID or PAY LATER) so '
             'the driver is never left guessing. Tick this to send an alert only '
             'when cash must be collected.',
    )
    cod_alert_skip_update = fields.Boolean(
        string='Do not re-alert when COD details change',
        config_parameter=PARAM_SKIP_UPDATE,
        help='By default an "UPDATED" alert is sent when the payment type, the '
             'amount to collect or the driver note of an already alerted order '
             'changes.',
    )

    # --- Shipping label -------------------------------------------------
    cod_label_hide_status = fields.Boolean(
        string='Hide payment status on the shipping label',
        config_parameter=PARAM_LABEL_HIDE,
    )
    cod_label_cod_text = fields.Char(
        string='Label text: Cash on Delivery',
        config_parameter=PARAM_LABEL_TEXT['cod'],
        default=LABEL_TEXT_DEFAULTS['cod'],
    )
    cod_label_paid_text = fields.Char(
        string='Label text: Already Paid',
        config_parameter=PARAM_LABEL_TEXT['paid'],
        default=LABEL_TEXT_DEFAULTS['paid'],
    )
    cod_label_credit_text = fields.Char(
        string='Label text: Pay Later',
        config_parameter=PARAM_LABEL_TEXT['credit'],
        default=LABEL_TEXT_DEFAULTS['credit'],
    )
