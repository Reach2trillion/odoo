# -*- coding: utf-8 -*-
from random import randint

from odoo import api, fields, models


class TelegramChatTag(models.Model):
    _name = 'telegram.chat.tag'
    _description = 'Telegram Chat Tag'
    _order = 'name, id'

    def _default_color(self):
        return randint(1, 11)

    name = fields.Char(required=True)
    color = fields.Integer(default=_default_color)
    active = fields.Boolean(default=True)
    chat_ids = fields.Many2many(
        'telegram.chat', 'telegram_chat_tag_rel', 'tag_id', 'chat_id', string='Chats')
    chat_count = fields.Integer(compute='_compute_chat_count')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'A tag with this name already exists.'),
    ]

    @api.depends('chat_ids')
    def _compute_chat_count(self):
        for tag in self:
            tag.chat_count = len(tag.chat_ids)
