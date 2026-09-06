# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.tools.misc import formatLang

from .common import LABEL_TEXT_DEFAULTS, PARAM_LABEL_HIDE, PARAM_LABEL_TEXT


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    cod_payment_type = fields.Selection(
        related='sale_id.cod_payment_type', string='Delivery Payment', store=True,
    )
    cod_currency_id = fields.Many2one(related='sale_id.currency_id')
    cod_amount = fields.Monetary(
        related='sale_id.cod_amount', string='Amount to Collect',
        currency_field='cod_currency_id', store=True,
    )
    cod_note = fields.Char(related='sale_id.cod_note', string='Driver Note (COD)')

    # ------------------------------------------------------------------
    # Triggers
    # ------------------------------------------------------------------
    def _action_done(self):
        res = super()._action_done()
        if self.env['sale.order']._cod_get_trigger() in ('validate', 'both'):
            for picking in self:
                if (
                    picking.picking_type_code == 'outgoing'
                    and picking.state == 'done'
                    and picking.sale_id
                ):
                    picking.sale_id._cod_send_alert('validate', picking=picking)
        return res

    def action_send_cod_alert(self):
        """Form button on the delivery order: (re)send the alert now."""
        errors = []
        for picking in self:
            if not picking.sale_id:
                errors.append(_('%s is not linked to a sales order.', picking.name))
                continue
            ok, error = picking.sale_id._cod_send_alert('manual', picking=picking)
            if not ok:
                errors.append('%s: %s' % (picking.name, error))
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
    # Shipping label
    # ------------------------------------------------------------------
    def _cod_get_label_values(self):
        """Values for the COD block of the 80x100mm shipping label.

        Returns ``False`` when nothing should be printed (not a delivery,
        no sales order, or the block is disabled in the settings).
        """
        self.ensure_one()
        helper = self.env['sale.cod.telegram']
        if self.picking_type_code != 'outgoing' or helper._get_bool_param(PARAM_LABEL_HIDE):
            return False
        order = self.sale_id.sudo()
        if not order:
            return False

        payment_type = order.cod_payment_type or 'cod'
        title = helper._get_param(PARAM_LABEL_TEXT[payment_type]) or LABEL_TEXT_DEFAULTS[payment_type]
        amount = ''
        if payment_type == 'cod' and order.cod_amount:
            amount = formatLang(self.env, order.cod_amount, currency_obj=order.currency_id)
        return {
            'type': payment_type,
            'title': title,
            'amount': amount,
            'note': order.cod_note or '',
        }
