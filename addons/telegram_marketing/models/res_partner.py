# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


class ResPartner(models.Model):
    _inherit = 'res.partner'

    telegram_username = fields.Char(string='Telegram Username', help="Telegram username, without the @ sign.")
    telegram_chat_ids = fields.One2many('telegram.chat', 'partner_id', string='Telegram Chats')
    telegram_chat_count = fields.Integer(compute='_compute_telegram_chat_count')

    @api.depends('telegram_chat_ids')
    def _compute_telegram_chat_count(self):
        counts = {partner.id: count for partner, count in self.env['telegram.chat']._read_group(
            [('partner_id', 'in', self.ids)], ['partner_id'], ['__count'])}
        for partner in self:
            partner.telegram_chat_count = counts.get(partner.id, 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('telegram_username'):
                vals['telegram_username'] = vals['telegram_username'].strip().lstrip('@')
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('telegram_username'):
            vals['telegram_username'] = vals['telegram_username'].strip().lstrip('@')
        return super().write(vals)

    def action_view_telegram_chats(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('telegram_marketing.telegram_chat_action')
        action['domain'] = [('partner_id', '=', self.id)]
        action['context'] = {'default_partner_id': self.id}
        if self.telegram_chat_count == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = self.telegram_chat_ids.id
        return action

    def action_send_telegram_message(self):
        chats = self.telegram_chat_ids.filtered(lambda c: not c.blocked)
        if not chats:
            bot = self.env['telegram.bot'].search([('state', '=', 'connected')], limit=1)
            hint = _("Ask them to open %s and press Start.", bot.start_link) if bot and bot.start_link else ''
            raise UserError(_("%(partner)s has no Telegram chat with your bot yet. %(hint)s",
                              partner=', '.join(self.mapped('display_name')), hint=hint).strip())
        action = self.env['ir.actions.actions']._for_xml_id('telegram_marketing.telegram_compose_action')
        action['context'] = {
            'default_bot_id': chats[0].bot_id.id,
            'default_chat_ids': [Command.set(chats.ids)],
        }
        return action
