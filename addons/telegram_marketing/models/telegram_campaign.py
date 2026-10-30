# -*- coding: utf-8 -*-
import json
import logging
import re
from ast import literal_eval
from collections import defaultdict

from markupsafe import Markup

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression

from .telegram_tools import html_to_telegram

_logger = logging.getLogger(__name__)


class TelegramCampaign(models.Model):
    _name = 'telegram.campaign'
    _description = 'Telegram Campaign'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Campaign', required=True, tracking=True)
    bot_id = fields.Many2one(
        'telegram.bot', string='Bot', required=True, tracking=True, ondelete='restrict',
        default=lambda self: self.env['telegram.bot'].search([], limit=1))
    company_id = fields.Many2one(related='bot_id.company_id', store=True)
    campaign_type = fields.Selection([
        ('promotion', 'Promotion'),
        ('announcement', 'Announcement'),
        ('other', 'Other'),
    ], string='Type', default='promotion', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sending', 'Sending'),
        ('done', 'Sent'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False)

    body = fields.Html(string='Message')
    attachment = fields.Binary(string='Image or File', attachment=True)
    attachment_filename = fields.Char()
    disable_preview = fields.Boolean(string='Hide Link Previews')
    button_ids = fields.One2many('telegram.campaign.button', 'campaign_id', string='Buttons', copy=True)

    recipient_mode = fields.Selection([
        ('all', 'All subscribers'),
        ('tags', 'Subscribers with tags'),
        ('domain', 'Custom filter'),
        ('manual', 'Selected chats'),
    ], string='Recipients', default='all', required=True)
    include_groups = fields.Boolean(
        string='Include Groups & Channels',
        help="Also post the message in the groups and channels the bot belongs to.")
    tag_ids = fields.Many2many(
        'telegram.chat.tag', 'telegram_campaign_tag_rel', 'campaign_id', 'tag_id', string='Tags')
    recipient_domain = fields.Char(string='Filter', default='[]')
    chat_ids = fields.Many2many(
        'telegram.chat', 'telegram_campaign_chat_rel', 'campaign_id', 'chat_id', string='Selected Chats')
    recipient_count = fields.Integer(compute='_compute_recipient_count')

    scheduled_date = fields.Datetime(tracking=True, copy=False)
    sent_date = fields.Datetime(string='Sending Started', readonly=True, copy=False)
    test_chat_id = fields.Many2one(
        'telegram.chat', string='Test Chat',
        help="Your own Telegram chat with the bot, to preview the campaign before sending it.")

    telegram_message_ids = fields.One2many('telegram.message', 'campaign_id', string='Telegram Messages')
    telegram_message_count = fields.Integer(compute='_compute_stats')
    sent_count = fields.Integer(string='Sent', compute='_compute_stats')
    failed_count = fields.Integer(string='Failed', compute='_compute_stats')
    pending_count = fields.Integer(string='Pending', compute='_compute_stats')
    cancelled_count = fields.Integer(string='Cancelled', compute='_compute_stats')
    progress = fields.Float(compute='_compute_stats')
    preview_text = fields.Html(string='Preview', compute='_compute_preview_text', sanitize=False)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends('bot_id', 'recipient_mode', 'include_groups', 'tag_ids', 'recipient_domain', 'chat_ids')
    def _compute_recipient_count(self):
        Chat = self.env['telegram.chat']
        for campaign in self:
            if not campaign.bot_id:
                campaign.recipient_count = 0
                continue
            try:
                campaign.recipient_count = Chat.search_count(campaign._get_recipient_domain())
            except (ValueError, SyntaxError, TypeError, UserError):
                campaign.recipient_count = 0

    @api.depends('telegram_message_ids.state')
    def _compute_stats(self):
        counts = defaultdict(lambda: defaultdict(int))
        for campaign, state, count in self.env['telegram.message']._read_group(
                [('campaign_id', 'in', self.ids)], ['campaign_id', 'state'], ['__count']):
            counts[campaign.id][state] += count
        for campaign in self:
            by_state = counts[campaign.id]
            total = sum(by_state.values())
            campaign.telegram_message_count = total
            campaign.sent_count = by_state['sent']
            campaign.failed_count = by_state['failed']
            campaign.pending_count = by_state['queued']
            campaign.cancelled_count = by_state['cancelled']
            finished = by_state['sent'] + by_state['failed'] + by_state['cancelled']
            campaign.progress = (finished * 100.0 / total) if total else 0.0

    @api.depends('body', 'test_chat_id', 'bot_id', 'attachment_filename', 'button_ids.name', 'button_ids.url')
    def _compute_preview_text(self):
        Message = self.env['telegram.message']
        Chat = self.env['telegram.chat']
        for campaign in self:
            chat = campaign.test_chat_id
            if not chat and campaign.bot_id:
                chat = Chat.search([('bot_id', '=', campaign.bot_id.id), ('chat_type', '=', 'private')], limit=1)
            try:
                telegram_html = (Message._render_html_for_chat(campaign.body, chat) if chat
                                 else html_to_telegram(campaign.body))
            except Exception as exc:  # noqa: BLE001 - show rendering problems instead of breaking the form
                campaign.preview_text = Markup('<div class="alert alert-danger" role="alert">%s</div>') % str(exc)
                continue
            parts = []
            if chat:
                parts.append(Markup('<div class="text-muted small mb-2">%s</div>') % _("Preview for %s", chat.display_name))
            if campaign.attachment_filename:
                parts.append(Markup('<div class="small mb-2">📎 %s</div>') % campaign.attachment_filename)
            body_html = tools.html_sanitize(telegram_html.replace('\n', '<br/>'), sanitize_attributes=True)
            parts.append(Markup('<div class="o_telegram_preview_bubble">%s</div>') % (body_html or _("(empty message)")))
            for button in campaign.button_ids:
                if button.name:
                    parts.append(Markup('<div class="o_telegram_preview_button">🔗 %s</div>') % button.name)
            campaign.preview_text = Markup('<div class="o_telegram_preview">%s</div>') % Markup('').join(parts)

    # ------------------------------------------------------------------
    # Recipients
    # ------------------------------------------------------------------

    def _get_recipient_domain(self):
        self.ensure_one()
        domain = [('bot_id', '=', self.bot_id.id), ('subscribed', '=', True), ('blocked', '=', False)]
        if not self.include_groups:
            domain.append(('chat_type', '=', 'private'))
        if self.recipient_mode == 'tags':
            domain.append(('tag_ids', 'in', self.tag_ids.ids))
        elif self.recipient_mode == 'domain':
            try:
                extra = literal_eval(self.recipient_domain) if self.recipient_domain else []
            except (ValueError, SyntaxError) as exc:
                raise UserError(_("The recipient filter is not valid: %s", exc))
            domain = expression.AND([domain, extra or []])
        elif self.recipient_mode == 'manual':
            domain.append(('id', 'in', self.chat_ids.ids))
        return domain

    def _get_recipients(self):
        self.ensure_one()
        return self.env['telegram.chat'].search(self._get_recipient_domain())

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    def _check_ready(self):
        for campaign in self:
            if not campaign.bot_id:
                raise UserError(_("Choose a bot first."))
            if campaign.bot_id.state != 'connected':
                raise UserError(_("The bot '%s' is not connected yet. Open it and click 'Check Connection'.",
                                  campaign.bot_id.name))
            if not campaign.bot_id._has_content(campaign.body) and not campaign.attachment:
                raise UserError(_("Write a message or attach a file before sending the campaign '%s'.", campaign.name))

    def _create_attachment(self):
        self.ensure_one()
        if not self.attachment:
            return None
        return self.env['ir.attachment'].create({
            'name': self.attachment_filename or _('attachment'),
            'datas': self.attachment,
            'res_model': self._name,
            'res_id': self.id,
        })

    def _get_reply_markup(self):
        self.ensure_one()
        rows = [[{'text': button.name, 'url': button.url}] for button in self.button_ids if button.name and button.url]
        return {'inline_keyboard': rows} if rows else None

    def _queue_messages(self, recipients):
        """Create one queued message per recipient, with the body rendered for each chat."""
        self.ensure_one()
        Message = self.env['telegram.message']
        rendered = Message._render_html_for_chats(self.body, recipients)
        attachment = self._create_attachment()
        buttons = self._get_reply_markup()
        now = fields.Datetime.now()
        values_list = []
        for chat in recipients:
            values_list.append({
                'chat_id': chat.id,
                'direction': 'out',
                'state': 'queued',
                'body': rendered.get(chat.id, ''),
                'message_type': ('photo' if Message._attachment_is_photo(attachment) else 'document') if attachment else 'text',
                'attachment_id': attachment.id if attachment else False,
                'buttons_json': json.dumps(buttons) if buttons else False,
                'disable_link_preview': self.disable_preview,
                'campaign_id': self.id,
                'author_id': self.env.user.id,
                'date': now,
            })
        return Message.create(values_list)

    def action_send_now(self):
        for campaign in self:
            if campaign.state not in ('draft', 'scheduled'):
                raise UserError(_("Only draft or scheduled campaigns can be sent."))
            campaign._check_ready()
            recipients = campaign._get_recipients()
            if not recipients:
                raise UserError(_(
                    "No recipient matches the campaign '%s'.\n"
                    "Customers receive campaigns once they pressed Start on your bot and stay subscribed.",
                    campaign.name))
            campaign._queue_messages(recipients)
            campaign.write({'state': 'sending', 'sent_date': fields.Datetime.now()})
            campaign.message_post(body=_("Sending to %s recipient(s).", len(recipients)))
        self.env['telegram.message']._trigger_send_cron()
        return True

    def action_schedule(self):
        for campaign in self:
            if campaign.state != 'draft':
                raise UserError(_("Only draft campaigns can be scheduled."))
            if not campaign.scheduled_date:
                raise UserError(_("Set a scheduled date first."))
            campaign._check_ready()
            if campaign.scheduled_date <= fields.Datetime.now():
                campaign.action_send_now()
            else:
                campaign.write({'state': 'scheduled'})
        return True

    def action_send_test(self):
        self.ensure_one()
        if not self.test_chat_id:
            raise UserError(_("Choose a test chat first: your own private chat with the bot."))
        self._check_ready()
        message = self.env['telegram.message']._send_html(
            self.test_chat_id, self.body, attachment=self._create_attachment(), buttons=self._get_reply_markup(),
            author=self.env.user, disable_link_preview=self.disable_preview)
        if message.state == 'failed':
            return self.bot_id._notification(_("Test message not delivered"), message.error or '', 'danger')
        return self.bot_id._notification(
            _("Test message sent"), _("Check the Telegram chat of %s.", self.test_chat_id.display_name))

    def action_cancel(self):
        for campaign in self:
            if campaign.state not in ('scheduled', 'sending'):
                raise UserError(_("Only scheduled or sending campaigns can be cancelled."))
            campaign.telegram_message_ids.filtered(lambda m: m.state == 'queued').write({'state': 'cancelled'})
            campaign.write({'state': 'cancelled'})
        return True

    def action_reset_draft(self):
        for campaign in self:
            if campaign.state not in ('scheduled', 'cancelled'):
                raise UserError(_("Only scheduled or cancelled campaigns can be reset to draft."))
            campaign.write({'state': 'draft'})
        return True

    def action_view_messages(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('telegram_marketing.telegram_message_action')
        action['domain'] = [('campaign_id', '=', self.id)]
        action['context'] = {'search_default_group_by_state': 1}
        return action

    def action_view_recipients(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('telegram_marketing.telegram_chat_action')
        action['domain'] = self._get_recipient_domain()
        action['context'] = {'default_bot_id': self.bot_id.id}
        return action

    # ------------------------------------------------------------------
    # Cron helpers
    # ------------------------------------------------------------------

    @api.model
    def _cron_launch_scheduled(self):
        due = self.search([('state', '=', 'scheduled'), ('scheduled_date', '<=', fields.Datetime.now())])
        for campaign in due:
            try:
                with self.env.cr.savepoint():
                    campaign.action_send_now()
            except Exception as exc:  # noqa: BLE001 - one broken campaign must not block the others
                _logger.exception("Telegram campaign %s could not be launched", campaign.name)
                campaign.message_post(body=_("Automatic sending failed: %s", exc))
        return True

    @api.model
    def _update_sending_states(self):
        for campaign in self.search([('state', '=', 'sending')]):
            if not campaign.pending_count:
                campaign.write({'state': 'done'})
                campaign.message_post(body=_(
                    "Campaign finished: %(sent)s sent, %(failed)s failed.",
                    sent=campaign.sent_count, failed=campaign.failed_count))
        return True


class TelegramCampaignButton(models.Model):
    _name = 'telegram.campaign.button'
    _description = 'Telegram Campaign Button'
    _order = 'sequence, id'

    campaign_id = fields.Many2one('telegram.campaign', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Button Text', required=True)
    url = fields.Char(string='Link', required=True)

    @api.constrains('url')
    def _check_url(self):
        for button in self:
            if not re.match(r'^(https?://|tg://)', button.url or '', re.I):
                raise ValidationError(_("Button links must start with http://, https:// or tg://"))
