# -*- coding: utf-8 -*-
from odoo import fields, models


class ChatflowTag(models.Model):
    _name = 'chatflow.tag'
    _description = 'ChatFlow Subscriber Tag'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    color = fields.Integer(string='Color Index')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Tag name already exists.'),
    ]
