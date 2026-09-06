# -*- coding: utf-8 -*-
"""Constants shared by the COD alert models."""

# How the customer pays for the delivery. Stored on the sales order,
# defaulted from the customer, mirrored on the delivery order.
COD_PAYMENT_TYPES = [
    ('cod', 'Cash on Delivery (collect cash)'),
    ('paid', 'Already Paid'),
    ('credit', 'Pay Later / Credit'),
]

# System parameter keys (all under one prefix so they are easy to find in
# Settings > Technical > System Parameters).
PARAM_CHAT_ID = 'sale_cod_telegram_alert.chat_id'
PARAM_BOT_TOKEN = 'sale_cod_telegram_alert.bot_token'
PARAM_TRIGGER = 'sale_cod_telegram_alert.trigger'
PARAM_ONLY_COD = 'sale_cod_telegram_alert.only_cod'
PARAM_SKIP_UPDATE = 'sale_cod_telegram_alert.skip_update_alert'
PARAM_LABEL_HIDE = 'sale_cod_telegram_alert.label_hide_status'
PARAM_LABEL_TEXT = {
    'cod': 'sale_cod_telegram_alert.label_cod_text',
    'paid': 'sale_cod_telegram_alert.label_paid_text',
    'credit': 'sale_cod_telegram_alert.label_credit_text',
}

# Parameters of other Telegram modules already installed on the database.
# They are read as a fallback only; this module does not depend on them.
FALLBACK_BOT_TOKEN_PARAM = 'send_by_telegram.bot_token'
FALLBACK_CHAT_ID_PARAM = 'delivery_packing_telegram.default_group_id'

TRIGGER_SELECTION = [
    ('confirm', 'When the sales order is confirmed (same moment as the packing message)'),
    ('validate', 'When the delivery order is validated'),
    ('both', 'Both'),
]
DEFAULT_TRIGGER = 'confirm'

# Bilingual (Khmer / English) texts printed on the shipping label. Kept short
# on purpose: the block is one line (text left, amount right) because the
# 80x100mm label is already full with a 4-line address.
LABEL_TEXT_DEFAULTS = {
    'cod': 'COD - ប្រមូលប្រាក់',
    'paid': 'PAID - បង់រួចហើយ - NO CASH',
    'credit': 'PAY LATER - បង់ពេលក្រោយ - NO CASH',
}
