# -*- coding: utf-8 -*-
import logging

from markupsafe import escape

from odoo import _, api, fields, models
from odoo.tools.misc import formatLang

from .common import (
    COD_PAYMENT_TYPES,
    DEFAULT_TRIGGER,
    PARAM_ONLY_COD,
    PARAM_SKIP_UPDATE,
    PARAM_TRIGGER,
)

_logger = logging.getLogger(__name__)

# Sales order fields whose change (after the first alert) triggers an
# "UPDATED" alert. ``order_line`` is watched because it changes the total,
# and therefore the amount to collect.
COD_WATCHED_FIELDS = {'cod_payment_type', 'cod_amount', 'cod_note', 'order_line'}

REASON_LABELS = {
    'confirm': 'order confirmed',
    'validate': 'delivery validated',
    'update': 'COD details updated',
    'manual': 'sent manually',
}


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cod_payment_type = fields.Selection(
        COD_PAYMENT_TYPES,
        string='Delivery Payment',
        required=True,
        compute='_compute_cod_payment_type',
        store=True,
        readonly=False,
        precompute=True,
        tracking=True,
        help='How the customer pays for this delivery. The driver is told by '
             'Telegram and on the shipping label whether cash must be collected.',
    )
    cod_amount = fields.Monetary(
        string='Amount to Collect',
        currency_field='currency_id',
        compute='_compute_cod_amount',
        store=True,
        readonly=False,
        tracking=True,
        help='Cash the driver must collect from the customer. Defaults to the '
             'order total for Cash on Delivery orders; lower it if the customer '
             'already paid a deposit. It is reset to the order total whenever '
             'the order lines change.',
    )
    cod_note = fields.Char(
        string='Driver Note (COD)',
        tracking=True,
        help='Printed on the shipping label and sent in the Telegram alert, '
             'e.g. "Customer pays in KHR" or "Call before delivery".',
    )
    cod_alert_sent = fields.Boolean(string='COD Alert Sent', copy=False, readonly=True)
    cod_alert_date = fields.Datetime(string='COD Alert Date', copy=False, readonly=True)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('partner_id')
    def _compute_cod_payment_type(self):
        for order in self:
            order.cod_payment_type = (
                order.partner_id.cod_payment_type or order.cod_payment_type or 'cod'
            )

    @api.depends('amount_total', 'cod_payment_type')
    def _compute_cod_amount(self):
        for order in self:
            order.cod_amount = order.amount_total if order.cod_payment_type == 'cod' else 0.0

    # ------------------------------------------------------------------
    # Triggers
    # ------------------------------------------------------------------
    def action_confirm(self):
        res = super().action_confirm()
        if self._cod_get_trigger() in ('confirm', 'both'):
            for order in self:
                order._cod_send_alert('confirm')
        return res

    def write(self, vals):
        snapshot = {}
        if COD_WATCHED_FIELDS & set(vals):
            snapshot = {
                order.id: order._cod_snapshot()
                for order in self
                if order.state == 'sale' and order.cod_alert_sent
            }
        res = super().write(vals)
        if snapshot and not self.env['sale.cod.telegram']._get_bool_param(PARAM_SKIP_UPDATE):
            for order in self:
                before = snapshot.get(order.id)
                if before is not None and before != order._cod_snapshot():
                    order._cod_send_alert('update')
        return res

    def _cod_snapshot(self):
        self.ensure_one()
        return (self.cod_payment_type, self.currency_id.round(self.cod_amount), self.cod_note or '')

    def action_send_cod_alert(self):
        """Form button: (re)send the alert now and tell the user how it went."""
        errors = []
        for order in self:
            ok, error = order._cod_send_alert('manual')
            if not ok:
                errors.append('%s: %s' % (order.name, error))
        if errors:
            message = _('Telegram alert failed. %s', ' | '.join(errors))
            notification_type = 'danger'
        else:
            message = _('Telegram COD alert sent.')
            notification_type = 'success'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('COD Delivery Alert'),
                'message': message,
                'type': notification_type,
                'sticky': False,
            },
        }

    # ------------------------------------------------------------------
    # Alert
    # ------------------------------------------------------------------
    @api.model
    def _cod_get_trigger(self):
        trigger = self.env['sale.cod.telegram']._get_param(PARAM_TRIGGER, DEFAULT_TRIGGER)
        return trigger if trigger in ('confirm', 'validate', 'both') else DEFAULT_TRIGGER

    def _cod_get_outgoing_pickings(self):
        return self.picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing' and p.state != 'cancel'
        )

    def _cod_send_alert(self, reason, picking=None):
        """Send the COD / PAID / PAY LATER alert for this order.

        :param reason: 'confirm', 'validate', 'update' or 'manual'
        :param picking: the delivery order concerned, when known
        :return: (ok, error_message); never raises.
        """
        self.ensure_one()
        order = self.sudo()
        helper = self.env['sale.cod.telegram']

        pickings = picking.sudo() if picking else order._cod_get_outgoing_pickings()
        if reason in ('confirm', 'validate'):
            if not pickings:
                return True, ''  # nothing to deliver (services, ...): no driver to warn
            if order.cod_payment_type != 'cod' and helper._get_bool_param(PARAM_ONLY_COD):
                return True, ''

        picking_type = pickings[:1].picking_type_id or order.warehouse_id.out_type_id
        chat_id = helper._get_chat_id(picking_type)
        text = order._cod_prepare_message(reason, pickings)
        ok, error = helper._send_message(chat_id, text)

        reason_label = REASON_LABELS.get(reason, reason)
        if ok:
            order.write({'cod_alert_sent': True, 'cod_alert_date': fields.Datetime.now()})
            order.message_post(
                body=_('COD delivery alert sent to Telegram (%s).', reason_label),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
        else:
            _logger.warning('COD Telegram alert for %s not sent (%s): %s', order.name, reason, error)
            order.message_post(
                body=_('COD delivery alert NOT sent to Telegram (%s): %s', reason_label, error),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
        return ok, error

    def _cod_prepare_message(self, reason, pickings):
        """Build the Telegram (HTML) text. Khmer + English so every driver reads it."""
        self.ensure_one()
        order = self.sudo()
        partner = order.partner_shipping_id or order.partner_id
        currency = order.currency_id

        def fmt(amount):
            return formatLang(self.env, amount, currency_obj=currency)

        def esc(value):
            return str(escape(value or ''))

        if order.cod_payment_type == 'cod':
            header = (
                '💵 <b>COD - ប្រមូលប្រាក់ពីអតិថិជន</b>\n'
                '<b>COLLECT CASH: %s</b>' % esc(fmt(order.cod_amount))
            )
        elif order.cod_payment_type == 'paid':
            header = (
                '✅ <b>PAID - បានបង់ប្រាក់រួចហើយ</b>\n'
                '<b>DO NOT collect money</b>'
            )
        else:
            header = (
                '🕓 <b>PAY LATER - បង់ប្រាក់ពេលក្រោយ</b>\n'
                '<b>DO NOT collect money at delivery</b>'
            )

        if reason == 'update':
            header = '⚠️ <b>UPDATED - បានកែប្រែ</b>\n' + header
        elif reason == 'validate':
            header = '🚚 <b>Out for delivery - ចេញដឹកជញ្ជូន</b>\n' + header

        reference = '🧾 %s' % esc(order.name)
        if pickings:
            reference += ' | 🚚 %s' % esc(', '.join(pickings.mapped('name')))

        lines = [header, '', reference, '👤 %s' % esc(partner.name)]
        phone = partner.phone or partner.mobile
        if phone:
            lines.append('📞 %s' % esc(phone))
        address = ' '.join(partner._display_address(without_company=True).split())
        if address:
            lines.append('📍 %s' % esc(address))
        lines.append('🛒 Order total: %s' % esc(fmt(order.amount_total)))
        if order.cod_payment_type == 'cod' and currency.compare_amounts(order.cod_amount, order.amount_total) != 0:
            lines.append('💰 <b>To collect: %s</b> (rest already paid)' % esc(fmt(order.cod_amount)))
        if order.cod_note:
            lines.append('📝 %s' % esc(order.cod_note))
        if order.user_id:
            lines.append('🧑‍💼 %s' % esc(order.user_id.name))
        return '\n'.join(lines)
