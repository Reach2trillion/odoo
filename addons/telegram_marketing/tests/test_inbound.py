# -*- coding: utf-8 -*-
import base64
import json

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TelegramCase, TINY_PNG


@tagged('standard', 'at_install', 'telegram')
class TestTelegramInbound(TelegramCase):

    def test_start_creates_chat_partner_and_welcome(self):
        update = self.make_message_update(2001, '/start', first_name='Charlie', username='charlie_k')
        self.bot._process_update(update)

        chat = self.env['telegram.chat'].search([('bot_id', '=', self.bot.id), ('chat_id', '=', '2001')])
        self.assertEqual(len(chat), 1)
        self.assertEqual(chat.name, 'Charlie')
        self.assertEqual(chat.username, 'charlie_k')
        self.assertEqual(chat.language_code, 'km')
        self.assertTrue(chat.subscribed)
        self.assertTrue(chat.partner_id, "a contact should be created automatically")
        self.assertEqual(chat.partner_id.telegram_username, 'charlie_k')
        self.assertEqual(self.bot.last_update_id, update['update_id'])

        sent = self.api.sent()
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]['params']['text'], 'Welcome Charlie!')
        self.assertEqual(sent[0]['params']['chat_id'], '2001')
        self.assertEqual(sent[0]['params']['parse_mode'], 'HTML')

        messages = chat.telegram_message_ids.sorted('id')
        self.assertEqual(messages.mapped('direction'), ['in', 'out'])
        self.assertEqual(messages[0].body, '/start')
        self.assertEqual(messages[1].state, 'sent')
        self.assertTrue(messages[1].is_auto)
        self.assertEqual(messages[1].telegram_message_id, '1001')
        self.assertEqual(chat.unread_count, 1)
        self.assertEqual(chat.last_message_preview, 'Welcome Charlie!')

    def test_start_payload_and_default_name_fallback(self):
        self.bot._process_update(self.make_message_update(2002, '/start shop_qr', first_name='Dara', username=None))
        chat = self.env['telegram.chat'].search([('bot_id', '=', self.bot.id), ('chat_id', '=', '2002')])
        self.assertEqual(chat.start_payload, 'shop_qr')
        self.assertEqual(chat.name, 'Dara')
        self.assertEqual(chat.display_name, 'Dara')

    def test_existing_username_links_partner(self):
        partner = self.env['res.partner'].create({'name': 'Known Customer', 'telegram_username': '@Known_User'})
        self.assertEqual(partner.telegram_username, 'Known_User')
        self.bot._process_update(self.make_message_update(2003, 'hi', first_name='K', username='known_user'))
        chat = self.env['telegram.chat'].search([('bot_id', '=', self.bot.id), ('chat_id', '=', '2003')])
        self.assertEqual(chat.partner_id, partner)
        self.assertEqual(partner.telegram_chat_count, 1)

    def test_stop_unsubscribes(self):
        self.bot._process_update(self.make_message_update(1001, '/stop@abj_test_bot'))
        self.assertFalse(self.chat_alice.subscribed)
        self.assertEqual(self.api.sent()[-1]['params']['text'], 'Bye')
        self.bot._process_update(self.make_message_update(1001, '/start'))
        self.assertTrue(self.chat_alice.subscribed)

    def test_auto_reply_keyword_khmer(self):
        rule = self.env['telegram.auto.reply'].create({
            'bot_id': self.bot.id, 'name': 'Price', 'keywords': 'price, តម្លៃ',
            'reply_body': '<p>Price list: <b>$10</b></p>',
            'button_text': 'Shop', 'button_url': 'https://example.com/shop',
        })
        self.bot._process_update(self.make_message_update(1001, 'តម្លៃប៉ុន្មាន?'))
        sent = self.api.sent()
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]['params']['text'], 'Price list: <b>$10</b>')
        self.assertEqual(sent[0]['params']['reply_markup'],
                         {'inline_keyboard': [[{'text': 'Shop', 'url': 'https://example.com/shop'}]]})
        out = self.chat_alice.telegram_message_ids.filtered(lambda m: m.direction == 'out')
        self.assertEqual(out.auto_reply_id, rule)
        self.assertEqual(rule.hit_count, 1)
        # Second rule is not used when the first matches; uppercase still matches.
        self.bot._process_update(self.make_message_update(1001, 'WHAT IS THE PRICE'))
        self.assertEqual(rule.hit_count, 2)

    def test_auto_reply_match_types(self):
        Rule = self.env['telegram.auto.reply']
        exact = Rule.create({'bot_id': self.bot.id, 'name': 'exact', 'keywords': 'menu', 'match_type': 'exact', 'reply_body': '<p>m</p>'})
        self.assertTrue(exact._matches(' Menu '))
        self.assertFalse(exact._matches('menu please'))
        starts = Rule.create({'bot_id': self.bot.id, 'name': 'starts', 'keywords': 'order', 'match_type': 'starts', 'reply_body': '<p>o</p>'})
        self.assertTrue(starts._matches('Order 12'))
        self.assertFalse(starts._matches('my order'))
        regex = Rule.create({'bot_id': self.bot.id, 'name': 'regex', 'keywords': r'^\d{4,}$', 'match_type': 'regex', 'reply_body': '<p>r</p>'})
        self.assertTrue(regex._matches('12345'))
        self.assertFalse(regex._matches('abc'))

    def test_no_rule_silent_then_default_reply(self):
        self.bot._process_update(self.make_message_update(1001, 'something unrelated'))
        self.assertEqual(self.api.sent(), [])
        self.bot.default_reply_body = '<p>We will answer soon.</p>'
        self.bot._process_update(self.make_message_update(1001, 'something unrelated'))
        self.assertEqual(self.api.sent()[-1]['params']['text'], 'We will answer soon.')

    def test_auto_reply_groups_only_when_enabled(self):
        self.env['telegram.auto.reply'].create({
            'bot_id': self.bot.id, 'name': 'Hello', 'keywords': 'hello', 'reply_body': '<p>Hi!</p>'})
        self.bot._process_update(self.make_message_update(-100500, 'hello all', chat_type='supergroup', title='ABJ Customers'))
        self.assertEqual(self.api.sent(), [], "no auto reply in groups by default")
        self.bot.auto_reply_in_groups = True
        self.bot._process_update(self.make_message_update(-100500, 'hello again', chat_type='supergroup', title='ABJ Customers'))
        self.assertEqual(len(self.api.sent()), 1)
        self.assertEqual(self.api.sent()[0]['params']['chat_id'], '-100500')

    def test_photo_is_downloaded(self):
        update = self.make_message_update(1001, None, photo=[
            {'file_id': 'small', 'width': 90, 'height': 90, 'file_size': 1000},
            {'file_id': 'big', 'width': 800, 'height': 600, 'file_size': 50000},
        ], caption='Is this one available?')
        self.bot._process_update(update)
        message = self.chat_alice.telegram_message_ids.filtered(lambda m: m.direction == 'in')
        self.assertEqual(message.message_type, 'photo')
        self.assertEqual(message.body, 'Is this one available?')
        self.assertEqual(message.telegram_file_id, 'big')
        self.assertTrue(message.attachment_id)
        self.assertEqual(message.attachment_id.raw, TINY_PNG)
        self.assertEqual(message.attachment_id.mimetype, 'image/jpeg')
        get_file = [call for call in self.api.calls if call['method'] == 'getFile']
        self.assertEqual(get_file[0]['params']['file_id'], 'big')
        self.assertTrue([call for call in self.api.calls if call['method'] == 'download'])
        self.assertIn('photos/file_1.jpg', [call for call in self.api.calls if call['method'] == 'download'][0]['url'])

    def test_media_download_can_be_disabled(self):
        self.bot.download_media = False
        self.bot._process_update(self.make_message_update(1001, None, document={
            'file_id': 'doc1', 'file_name': 'order.pdf', 'mime_type': 'application/pdf', 'file_size': 2000}))
        message = self.chat_alice.telegram_message_ids.filtered(lambda m: m.direction == 'in')
        self.assertEqual(message.message_type, 'document')
        self.assertFalse(message.attachment_id)
        self.assertFalse([call for call in self.api.calls if call['method'] == 'getFile'])

    def test_other_message_types(self):
        self.bot._process_update(self.make_message_update(1001, None, sticker={'file_id': 's', 'emoji': '😀'}))
        self.bot._process_update(self.make_message_update(1001, None, location={'latitude': 11.56, 'longitude': 104.92}))
        self.bot._process_update(self.make_message_update(1001, None, new_chat_members=[{'id': 5, 'first_name': 'X'}]))
        messages = self.chat_alice.telegram_message_ids.filtered(lambda m: m.direction == 'in').sorted('id')
        self.assertEqual(messages.mapped('message_type'), ['sticker', 'location'], "service messages are ignored")
        self.assertEqual(messages[0].body, '😀 [sticker]')
        self.assertIn('11.56,104.92', messages[1].body)

    def test_contact_matches_partner_by_phone(self):
        partner = self.env['res.partner'].create({'name': 'Phone Customer', 'phone': '+855 77 123 456'})
        self.bot._process_update(self.make_message_update(2010, None, first_name='Phone', username=None, contact={
            'phone_number': '+85577123456', 'first_name': 'Phone', 'user_id': 2010}))
        chat = self.env['telegram.chat'].search([('bot_id', '=', self.bot.id), ('chat_id', '=', '2010')])
        self.assertEqual(chat.partner_id, partner)
        self.assertEqual(chat.telegram_message_ids.message_type, 'contact')

    def test_contact_creates_partner_with_phone(self):
        self.bot.auto_create_partner = False
        self.bot._process_update(self.make_message_update(2011, 'hi', first_name='Nobody', username=None))
        chat = self.env['telegram.chat'].search([('bot_id', '=', self.bot.id), ('chat_id', '=', '2011')])
        self.assertFalse(chat.partner_id)
        self.bot.auto_create_partner = True
        self.bot._process_update(self.make_message_update(2011, None, first_name='Nobody', username=None, contact={
            'phone_number': '+855 99 000 111', 'first_name': 'Nobody', 'last_name': 'Known'}))
        self.assertEqual(chat.partner_id.name, 'Nobody Known')
        self.assertEqual(chat.partner_id.phone, '+855 99 000 111')

    def test_duplicate_update_is_ignored(self):
        update = self.make_message_update(1001, 'hello', message_id=42)
        self.bot._process_update(update)
        self.bot._process_update(update)
        self.assertEqual(len(self.chat_alice.telegram_message_ids.filtered(lambda m: m.direction == 'in')), 1)

    def test_messages_from_bots_are_ignored(self):
        self.bot._process_update(self.make_message_update(1001, 'spam', is_bot=True))
        self.assertFalse(self.chat_alice.telegram_message_ids)

    def test_my_chat_member_blocked_and_unblocked(self):
        self.bot._process_update(self.make_chat_member_update(1001, 'kicked'))
        self.assertTrue(self.chat_alice.blocked)
        self.bot._process_update(self.make_chat_member_update(1001, 'member'))
        self.assertFalse(self.chat_alice.blocked)
        # bot added to a new channel -> chat record created
        self.bot._process_update(self.make_chat_member_update(-1001234, 'administrator', chat_type='channel'))
        channel = self.env['telegram.chat'].search([('bot_id', '=', self.bot.id), ('chat_id', '=', '-1001234')])
        self.assertEqual(channel.chat_type, 'channel')
        self.assertFalse(channel.blocked)
        self.assertFalse(channel.partner_id, "no contact for groups and channels")

    def test_unread_counter_and_mark_read(self):
        self.bot._process_update(self.make_message_update(1001, 'one'))
        self.bot._process_update(self.make_message_update(1001, 'two'))
        self.assertEqual(self.chat_alice.unread_count, 2)
        self.assertEqual(self.chat_alice.last_message_preview, 'two')
        self.chat_alice.action_mark_read()
        self.assertEqual(self.chat_alice.unread_count, 0)

    def test_bus_notification_is_sent(self):
        self.bot._process_update(self.make_message_update(1001, 'ping'))
        # bus.bus rows are created at pre-commit; inspect the pending values
        pending = self.env.cr.precommit.data.get('bus.bus.values', [])
        ours = [value for value in pending if 'telegram_marketing/new_message' in value['message']]
        self.assertTrue(ours)
        group = self.env.ref('telegram_marketing.group_telegram_user')
        self.assertEqual(json.loads(ours[-1]['channel'])[1:], ['res.groups', group.id])
        payload = json.loads(ours[-1]['message'])
        self.assertEqual(payload['type'], 'telegram_marketing/new_message')
        self.assertEqual(payload['payload']['chat_id'], self.chat_alice.id)
        self.assertEqual(payload['payload']['direction'], 'in')

    def test_send_reply_from_chat_form(self):
        chat = self.chat_alice.with_user(self.user_marketing)
        chat.write({'reply_text': 'Hi <there> & welcome'})
        chat.action_send_reply()
        sent = self.api.sent()
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]['params']['text'], 'Hi &lt;there&gt; &amp; welcome')
        self.assertFalse(chat.reply_text)
        message = chat.telegram_message_ids
        self.assertEqual(message.state, 'sent')
        self.assertEqual(message.author_id, self.user_marketing)
        self.assertEqual(message.preview, 'Hi <there> & welcome')
        self.assertEqual(chat.unread_count, 0)
        self.assertEqual(str(chat.conversation_html).count('o_telegram_msg_out'), 1)
        self.assertIn('Hi &lt;there&gt; &amp; welcome', chat.get_conversation_html())

    def test_send_reply_with_attachment(self):
        self.chat_alice.write({
            'reply_text': 'Here is the catalog',
            'reply_attachment': base64.b64encode(TINY_PNG),
            'reply_attachment_name': 'catalog.png',
        })
        self.chat_alice.action_send_reply()
        sent = self.api.sent()
        self.assertEqual(sent[0]['method'], 'sendPhoto')
        self.assertEqual(sent[0]['params']['caption'], 'Here is the catalog')
        self.assertEqual(sent[0]['files']['photo'][0], 'catalog.png')
        self.assertEqual(sent[0]['files']['photo'][1], TINY_PNG)
        message = self.chat_alice.telegram_message_ids
        self.assertEqual(message.message_type, 'photo')
        self.assertFalse(self.chat_alice.reply_attachment)

    def test_empty_reply_refused(self):
        with self.assertRaises(UserError):
            self.chat_alice.action_send_reply()

    def test_blocked_on_403(self):
        self.api.failures['1002'] = (403, 'Forbidden: bot was blocked by the user')
        message = self.env['telegram.message']._send_text(self.chat_bob, 'promo')
        self.assertEqual(message.state, 'failed')
        self.assertIn('blocked', message.error)
        self.assertTrue(self.chat_bob.blocked)
        with self.assertRaises(UserError):
            self.chat_bob.write({'reply_text': 'again'})
            self.chat_bob.action_send_reply()

    def test_polling_cron(self):
        self.bot.update_mode = 'polling'
        self.api.updates = [
            self.make_message_update(1001, 'first'),
            self.make_message_update(1002, 'second', first_name='Bob', username=None),
        ]
        last = self.api.updates[-1]['update_id']
        self.env['telegram.bot']._cron_poll_updates()
        self.assertEqual(self.bot.last_update_id, last)
        self.assertEqual(self.chat_alice.telegram_message_ids.body, 'first')
        self.assertEqual(self.chat_bob.telegram_message_ids.body, 'second')
        get_updates = [call for call in self.api.calls if call['method'] == 'getUpdates']
        self.assertEqual(len(get_updates), 1)
        self.assertEqual(get_updates[0]['params']['allowed_updates'], ['message', 'channel_post', 'my_chat_member'])
        # next poll uses the offset
        self.env['telegram.bot']._cron_poll_updates()
        self.assertEqual([call for call in self.api.calls if call['method'] == 'getUpdates'][-1]['params']['offset'], last + 1)

    def test_polling_cron_skips_webhook_bots(self):
        self.api.updates = [self.make_message_update(1001, 'first')]
        self.env['telegram.bot']._cron_poll_updates()
        self.assertFalse([call for call in self.api.calls if call['method'] == 'getUpdates'])

    def test_manual_chat_resolution(self):
        self.api.chat_info['@abjchannel'] = {'id': -1001000, 'type': 'channel', 'title': 'ABJ Channel', 'username': 'abjchannel'}
        chat = self.env['telegram.chat']._get_or_create_manual(self.bot, 'abjchannel')
        self.assertEqual(chat.chat_id, '-1001000')
        self.assertEqual(chat.chat_type, 'channel')
        self.assertEqual(chat.name, 'ABJ Channel')
        # second call reuses the record without calling Telegram again
        calls_before = len(self.api.calls)
        self.assertEqual(self.env['telegram.chat']._get_or_create_manual(self.bot, '@AbjChannel'), chat)
        self.assertEqual(len(self.api.calls), calls_before)
        with self.assertRaises(UserError):
            self.env['telegram.chat']._get_or_create_manual(self.bot, '@unknown')

    def test_check_connection_and_webhook(self):
        bot = self.env['telegram.bot'].create({'name': 'Second', 'token': '987654321:ANOTHERTOKEN_abcdefghijklmnopqrstuv'})
        bot.action_check_connection()
        self.assertEqual(bot.state, 'connected')
        self.assertEqual(bot.username, 'abj_test_bot')
        self.assertEqual(bot.telegram_id, '777')
        self.assertIn('https://t.me/abj_test_bot', bot.start_link)
        self.assertIn('/report/barcode/', str(bot.start_qr_html))
        self.env['ir.config_parameter'].sudo().set_param('web.base.url', 'https://odoo.example.com')
        bot.invalidate_recordset(['webhook_url'])
        self.assertTrue(bot.webhook_url.startswith('https://odoo.example.com/telegram/webhook/%s/' % bot.id))
        bot.action_set_webhook()
        set_webhook = [call for call in self.api.calls if call['method'] == 'setWebhook'][0]
        self.assertEqual(set_webhook['params']['url'], bot.webhook_url)
        self.assertEqual(set_webhook['params']['secret_token'], bot.webhook_secret)
        self.assertTrue(bot.webhook_set)
        bot.action_use_polling()
        self.assertEqual(bot.update_mode, 'polling')
        self.assertFalse(bot.webhook_set)

    def test_token_is_never_in_error_messages(self):
        from requests import ConnectionError as RequestsConnectionError

        def failing_post(url, **kwargs):
            raise RequestsConnectionError('Max retries exceeded with url: %s' % url)

        from unittest.mock import patch
        with patch('requests.post', side_effect=failing_post):
            message = self.env['telegram.message']._send_text(self.chat_alice, 'x')
        self.assertEqual(message.state, 'failed')
        self.assertNotIn('TESTTOKEN', message.error)
        self.assertIn('<token>', message.error)
