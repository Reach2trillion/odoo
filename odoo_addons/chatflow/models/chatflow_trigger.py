# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ChatflowTrigger(models.Model):
    _name = 'chatflow.trigger'
    _description = 'ChatFlow Trigger'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    trigger_type = fields.Selection([
        ('keyword', 'Keywords'),
        ('welcome', 'Welcome (Get Started button)'),
        ('default', 'Default Reply (no keyword matched)'),
    ], required=True, default='keyword')
    keywords = fields.Char(
        help="Comma-separated keywords, e.g.: price, តម្លៃ, how much")
    match_type = fields.Selection([
        ('contains', 'Message contains the keyword'),
        ('starts', 'Message starts with the keyword'),
        ('exact', 'Message is exactly the keyword'),
    ], default='contains', required=True)
    apply_to_comments = fields.Boolean(
        string='Also Reply to Comments', default=True,
        help="Also use this trigger to auto-reply to comments on Page "
             "posts (when enabled on the page).")
    page_id = fields.Many2one(
        'chatflow.page', string='Page', ondelete='cascade',
        help="Leave empty to apply this trigger to every connected page.")
    flow_id = fields.Many2one(
        'chatflow.flow', string='Flow to Start', required=True,
        ondelete='cascade')
    hit_count = fields.Integer(readonly=True, copy=False)

    def _keyword_list(self):
        self.ensure_one()
        return [keyword.strip().lower()
                for keyword in (self.keywords or '').split(',')
                if keyword.strip()]

    def _matches(self, text):
        self.ensure_one()
        for keyword in self._keyword_list():
            if self.match_type == 'exact' and text == keyword:
                return True
            if self.match_type == 'starts' and text.startswith(keyword):
                return True
            if self.match_type == 'contains' and keyword in text:
                return True
        return False

    @api.model
    def _page_domain(self, page):
        return ['|', ('page_id', '=', False), ('page_id', '=', page.id)]

    @api.model
    def _match_keyword(self, page, text, comments_only=False):
        """Return the first keyword trigger matching `text`, or the default
        trigger when nothing matches."""
        text = (text or '').strip().lower()
        domain = [('trigger_type', '=', 'keyword')] + self._page_domain(page)
        if comments_only:
            domain.append(('apply_to_comments', '=', True))
        for trigger in self.sudo().search(domain):
            if trigger._matches(text):
                return trigger
        default_domain = ([('trigger_type', '=', 'default')]
                          + self._page_domain(page))
        if comments_only:
            default_domain.append(('apply_to_comments', '=', True))
        return self.sudo().search(default_domain, limit=1)

    @api.model
    def _get_welcome(self, page):
        return self.sudo().search(
            [('trigger_type', '=', 'welcome')] + self._page_domain(page),
            limit=1)

    def _fire(self, subscriber, messaging_type='RESPONSE', tag=None):
        """Run the trigger's flow and update statistics."""
        self.ensure_one()
        self.sudo().hit_count += 1
        return self.flow_id.run(
            subscriber, messaging_type=messaging_type, tag=tag)
