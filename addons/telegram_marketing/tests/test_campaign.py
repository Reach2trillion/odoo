# -*- coding: utf-8 -*-
import base64
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import TelegramCase, TINY_PNG


@tagged('standard', 'at_install', 'telegram')
class TestTelegramCampaign(TelegramCase):

    def _campaign(self, **values):
        base = {
            'name': 'Promo',
            'bot_id': self.bot.id,
            'body': '<p>Hi {{ object.first_name ||| there }}, <b>20% off</b> this week!</p>',
        }
        base.update(values)
        return self.env['telegram.campaign'].create(base)

    def test_recipient_modes(self):
        campaign = self._campaign()
        self.assertEqual(campaign._get_recipients(), self.chat_alice | self.chat_bob)
        self.assertEqual(campaign.recipient_count, 2)
        campaign.include_groups = True
        self.assertEqual(campaign._get_recipients(), self.chat_alice | self.chat_bob | self.chat_group)
        campaign.write({'include_groups': False, 'recipient_mode': 'tags', 'tag_ids': [(6, 0, [self.tag_vip.id])]})
        self.assertEqual(campaign._get_recipients(), self.chat_alice)
        campaign.write({'recipient_mode': 'manual', 'chat_ids': [(6, 0, [self.chat_bob.id])]})
        self.assertEqual(campaign._get_recipients(), self.chat_bob)
        campaign.write({'recipient_mode': 'domain', 'recipient_domain': "[('username', '=', 'alice')]"})
        self.assertEqual(campaign._get_recipients(), self.chat_alice)
        campaign.write({'recipient_mode': 'all'})
        self.chat_bob.subscribed = False
        self.assertEqual(campaign._get_recipients(), self.chat_alice)
        self.chat_alice.blocked = True
        self.assertFalse(campaign._get_recipients())
        self.assertEqual(campaign.recipient_count, 0)

    def test_send_now_and_cron(self):
        campaign = self._campaign(button_ids=[(0, 0, {'name': 'Shop', 'url': 'https://example.com/shop'})])
        campaign.action_send_now()
        self.assertEqual(campaign.state, 'sending')
        self.assertTrue(campaign.sent_date)
        queued = campaign.telegram_message_ids
        self.assertEqual(len(queued), 2)
        self.assertEqual(set(queued.mapped('state')), {'queued'})
        self.assertEqual(campaign.pending_count, 2)
        trigger = self.env['ir.cron.trigger'].search([
            ('cron_id', '=', self.env.ref('telegram_marketing.ir_cron_telegram_send_queue').id)])
        self.assertTrue(trigger, "the sender cron is triggered right away")
        self.assertFalse(self.api.sent(), "nothing is sent before the cron runs")

        self.env['telegram.message']._cron_send_queue()
        self.assertEqual(set(campaign.telegram_message_ids.mapped('state')), {'sent'})
        self.assertEqual(campaign.state, 'done')
        self.assertEqual(campaign.sent_count, 2)
        self.assertEqual(campaign.failed_count, 0)
        self.assertEqual(campaign.progress, 100.0)
        texts = sorted(call['params']['text'] for call in self.api.sent())
        self.assertEqual(texts, ['Hi Alice, <b>20% off</b> this week!', 'Hi Bob, <b>20% off</b> this week!'])
        for call in self.api.sent():
            self.assertEqual(call['params']['reply_markup'],
                             {'inline_keyboard': [[{'text': 'Shop', 'url': 'https://example.com/shop'}]]})
        self.assertTrue(campaign.message_ids.filtered(lambda m: 'Campaign finished' in (m.body or '')))
        self.assertEqual(self.chat_alice.last_message_preview, 'Hi Alice, 20% off this week!')
        self.assertEqual(self.chat_alice.unread_count, 0, "campaign messages do not touch the unread counter")

    def test_placeholder_default_when_empty(self):
        self.chat_bob.first_name = False
        campaign = self._campaign(recipient_mode='manual', chat_ids=[(6, 0, [self.chat_bob.id])])
        campaign.action_send_now()
        self.env['telegram.message']._cron_send_queue()
        self.assertEqual(self.api.sent()[0]['params']['text'], 'Hi there, <b>20% off</b> this week!')

    def test_campaign_with_photo(self):
        campaign = self._campaign(attachment=base64.b64encode(TINY_PNG), attachment_filename='promo.png',
                                  recipient_mode='manual', chat_ids=[(6, 0, [self.chat_alice.id])])
        campaign.action_send_now()
        self.env['telegram.message']._cron_send_queue()
        sent = self.api.sent()
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]['method'], 'sendPhoto')
        self.assertEqual(sent[0]['params']['caption'], 'Hi Alice, <b>20% off</b> this week!')
        self.assertEqual(sent[0]['files']['photo'][1], TINY_PNG)
        self.assertEqual(campaign.telegram_message_ids.message_type, 'photo')
        self.assertEqual(campaign.telegram_message_ids.attachment_id.res_model, 'telegram.campaign')

    def test_campaign_with_document_and_long_text(self):
        long_body = '<p>%s</p>' % ('word ' * 400)
        campaign = self._campaign(body=long_body, attachment=base64.b64encode(b'%PDF-1.4 fake'),
                                  attachment_filename='catalog.pdf', recipient_mode='manual',
                                  chat_ids=[(6, 0, [self.chat_alice.id])])
        campaign.action_send_now()
        self.env['telegram.message']._cron_send_queue()
        methods = [call['method'] for call in self.api.sent()]
        self.assertEqual(methods, ['sendDocument', 'sendMessage'], "long caption: document first, then the text")
        self.assertNotIn('caption', self.api.sent()[0]['params'])
        self.assertEqual(campaign.telegram_message_ids.state, 'sent')

    def test_failed_recipient_marks_chat_blocked(self):
        self.api.failures['1002'] = (403, 'Forbidden: bot was blocked by the user')
        campaign = self._campaign()
        campaign.action_send_now()
        self.env['telegram.message']._cron_send_queue()
        self.assertEqual(campaign.state, 'done')
        self.assertEqual(campaign.sent_count, 1)
        self.assertEqual(campaign.failed_count, 1)
        self.assertTrue(self.chat_bob.blocked)
        failed = campaign.telegram_message_ids.filtered(lambda m: m.state == 'failed')
        self.assertEqual(failed.chat_id, self.chat_bob)
        self.assertIn('blocked', failed.error)
        # retry after the customer came back
        self.api.failures.clear()
        self.chat_bob.blocked = False
        failed.action_retry()
        self.assertEqual(failed.state, 'queued')
        self.env['telegram.message']._cron_send_queue()
        self.assertEqual(failed.state, 'sent')

    def test_rate_limit_pauses_the_queue(self):
        self.api.rate_limit_remaining = 1
        campaign = self._campaign()
        campaign.action_send_now()
        cron = self.env.ref('telegram_marketing.ir_cron_telegram_send_queue')
        self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)]).unlink()

        self.env['telegram.message']._cron_send_queue()
        self.assertEqual(campaign.state, 'sending')
        self.assertEqual(campaign.pending_count, 2, "the rate-limited message stays queued and the batch stops")
        self.assertEqual(len(self.api.sent()), 1)
        triggers = self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])
        self.assertTrue(triggers)
        self.assertGreater(triggers[0].call_at, fields.Datetime.now() + timedelta(seconds=1))

        self.env['telegram.message']._cron_send_queue()
        self.assertEqual(campaign.state, 'done')
        self.assertEqual(campaign.sent_count, 2)

    def test_schedule(self):
        campaign = self._campaign(scheduled_date=fields.Datetime.now() + timedelta(days=1))
        campaign.action_schedule()
        self.assertEqual(campaign.state, 'scheduled')
        self.env['telegram.message']._cron_send_queue()
        self.assertEqual(campaign.state, 'scheduled', "not due yet")
        self.assertFalse(self.api.sent())
        campaign.scheduled_date = fields.Datetime.now() - timedelta(minutes=1)
        self.env['telegram.message']._cron_send_queue()
        self.assertEqual(campaign.state, 'done')
        self.assertEqual(len(self.api.sent()), 2)

    def test_schedule_in_the_past_sends_now(self):
        campaign = self._campaign(scheduled_date=fields.Datetime.now() - timedelta(minutes=1))
        campaign.action_schedule()
        self.assertEqual(campaign.state, 'sending')

    def test_cancel_and_reset(self):
        campaign = self._campaign()
        campaign.action_send_now()
        campaign.action_cancel()
        self.assertEqual(campaign.state, 'cancelled')
        self.assertEqual(set(campaign.telegram_message_ids.mapped('state')), {'cancelled'})
        self.env['telegram.message']._cron_send_queue()
        self.assertFalse(self.api.sent())
        campaign.action_reset_draft()
        self.assertEqual(campaign.state, 'draft')

    def test_checks_before_sending(self):
        with self.assertRaises(UserError):
            self._campaign(body='<p><br/></p>').action_send_now()
        self.bot.state = 'draft'
        with self.assertRaises(UserError):
            self._campaign().action_send_now()
        self.bot.state = 'connected'
        campaign = self._campaign(recipient_mode='tags', tag_ids=[(6, 0, [self.env['telegram.chat.tag'].create({'name': 'Empty'}).id])])
        with self.assertRaises(UserError):
            campaign.action_send_now()
        with self.assertRaises(UserError):
            self._campaign().action_schedule()

    def test_send_test(self):
        campaign = self._campaign(test_chat_id=self.chat_alice.id)
        result = campaign.action_send_test()
        self.assertEqual(result['params']['type'], 'success')
        sent = self.api.sent()
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]['params']['text'], 'Hi Alice, <b>20% off</b> this week!')
        self.assertFalse(campaign.telegram_message_ids, "test messages are not part of the campaign statistics")
        self.assertEqual(self.chat_alice.telegram_message_ids.author_id, self.env.user)

    def test_preview(self):
        campaign = self._campaign(test_chat_id=self.chat_alice.id,
                                  button_ids=[(0, 0, {'name': 'Shop', 'url': 'https://example.com'})])
        preview = str(campaign.preview_text)
        self.assertIn('Hi Alice, <b>20% off</b> this week!', preview)
        self.assertIn('Shop', preview)
        self.assertIn('Preview for', preview)

    def test_restricted_user_simple_placeholders_allowed(self):
        campaign = self._campaign().with_user(self.user_marketing)
        campaign.action_send_now()
        self.env['telegram.message']._cron_send_queue()
        self.assertEqual(campaign.state, 'done')
        self.assertEqual(len(self.api.sent()), 2)

    def test_restricted_user_complex_expression_refused(self):
        campaign = self._campaign(body='<p>{{ object.first_name.upper() }}</p>').with_user(self.user_marketing)
        with self.assertRaises(AccessError):
            campaign.action_send_now()

    def test_button_url_validation(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self._campaign(button_ids=[(0, 0, {'name': 'Bad', 'url': 'javascript:alert(1)'})])

    def test_compose_wizard(self):
        self.api.chat_info['@abjchannel'] = {'id': -1001000, 'type': 'channel', 'title': 'ABJ Channel', 'username': 'abjchannel'}
        wizard = self.env['telegram.compose'].with_context(
            active_model='telegram.chat', active_ids=[self.chat_alice.id, self.chat_bob.id]).create({
                'body': '<p>Hello {{ object.first_name ||| there }} 👋</p>',
                'manual_chat_id': '@abjchannel',
                'button_text': 'Shop', 'button_url': 'https://example.com',
            })
        self.assertEqual(wizard.chat_ids, self.chat_alice | self.chat_bob)
        self.assertEqual(wizard.bot_id, self.bot)
        self.assertEqual(wizard.recipient_count, 3)
        result = wizard.action_send()
        self.assertEqual(result['params']['type'], 'success')
        texts = sorted(call['params']['text'] for call in self.api.sent())
        self.assertEqual(texts, ['Hello Alice 👋', 'Hello Bob 👋', 'Hello there 👋'])
        channel = self.env['telegram.chat'].search([('bot_id', '=', self.bot.id), ('chat_id', '=', '-1001000')])
        self.assertEqual(channel.chat_type, 'channel')
        self.assertEqual(channel.telegram_message_ids.state, 'sent')

    def test_compose_wizard_from_partner(self):
        partner = self.env['res.partner'].create({'name': 'Alice Partner'})
        self.chat_alice.partner_id = partner
        self.assertEqual(partner.telegram_username, 'alice', "username copied to the contact")
        action = partner.action_send_telegram_message()
        wizard = self.env['telegram.compose'].with_context(action['context']).create({'body': '<p>Hi</p>'})
        self.assertEqual(wizard.chat_ids, self.chat_alice)
        wizard.action_send()
        self.assertEqual(self.api.sent()[0]['params']['chat_id'], '1001')
        with self.assertRaises(UserError):
            self.env['res.partner'].create({'name': 'No Telegram'}).action_send_telegram_message()

    def test_compose_wizard_requires_recipient_and_content(self):
        with self.assertRaises(UserError):
            self.env['telegram.compose'].create({'bot_id': self.bot.id, 'body': '<p>x</p>'}).action_send()
        with self.assertRaises(UserError):
            self.env['telegram.compose'].create({'bot_id': self.bot.id, 'chat_ids': [(6, 0, [self.chat_alice.id])]}).action_send()
