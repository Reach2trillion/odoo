# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged

from odoo.addons.telegram_marketing.models.telegram_tools import (
    escape_text, html_to_telegram, split_text, telegram_html_to_text, TelegramError,
)


@tagged('standard', 'at_install', 'telegram')
class TestTelegramTools(TransactionCase):

    def test_basic_formatting(self):
        self.assertEqual(html_to_telegram('<p>Hello <b>World</b></p><p>Second</p>'), 'Hello <b>World</b>\nSecond')
        self.assertEqual(html_to_telegram('<p>Line1<br/>Line2</p>'), 'Line1\nLine2')
        self.assertEqual(html_to_telegram('<p><strong>a</strong> <em>b</em> <u>c</u> <s>d</s> <code>e</code></p>'),
                         '<b>a</b> <i>b</i> <u>c</u> <s>d</s> <code>e</code>')
        self.assertEqual(html_to_telegram('<h1>Title</h1><p>Text</p>'), '<b>Title</b>\nText')
        self.assertEqual(html_to_telegram('<blockquote>quoted</blockquote>'), '<blockquote>quoted</blockquote>')

    def test_lists(self):
        self.assertEqual(html_to_telegram('<ul><li>One</li><li>Two</li></ul>'), '• One\n• Two')
        self.assertEqual(html_to_telegram('<ol><li>One</li><li>Two</li></ol>'), '1. One\n2. Two')

    def test_escaping(self):
        self.assertEqual(html_to_telegram('<p>A &amp; B &lt; C</p>'), 'A &amp; B &lt; C')
        self.assertEqual(html_to_telegram('<p>5 > 3</p>'), '5 &gt; 3')
        self.assertEqual(escape_text('<b>&'), '&lt;b&gt;&amp;')
        self.assertEqual(telegram_html_to_text('<b>a &amp; b</b>'), 'a & b')

    def test_links(self):
        self.assertEqual(html_to_telegram('<a href="https://abj.com/shop?a=1&amp;b=2">Shop</a>'),
                         '<a href="https://abj.com/shop?a=1&amp;b=2">Shop</a>')
        self.assertEqual(html_to_telegram('<a href="javascript:alert(1)">x</a>'), 'x')
        self.assertEqual(html_to_telegram('<a>no href</a>'), 'no href')

    def test_empty_and_unknown_tags(self):
        self.assertEqual(html_to_telegram('<p><b></b>empty</p>'), 'empty')
        self.assertEqual(html_to_telegram('<script>alert(1)</script><p>safe</p>'), 'safe')
        self.assertEqual(html_to_telegram('<p>  spaced   text </p>'), 'spaced text')
        self.assertEqual(html_to_telegram('<div><span style="color:red">styled</span></div>'), 'styled')
        self.assertEqual(html_to_telegram('<p>a</p><p><br/></p><p>b</p>'), 'a\n\nb')
        self.assertEqual(html_to_telegram(''), '')
        self.assertEqual(html_to_telegram(False), '')
        self.assertEqual(html_to_telegram('plain text'), 'plain text')

    def test_khmer_and_emoji(self):
        self.assertEqual(html_to_telegram('<p>សួស្តី <i>ABJ</i> 👋</p>'), 'សួស្តី <i>ABJ</i> 👋')
        self.assertEqual(html_to_telegram('<p>Hello {{ object.first_name ||| there }}!</p>'),
                         'Hello {{ object.first_name ||| there }}!')

    def test_split_text(self):
        text = '\n'.join('line %s' % index for index in range(1000))
        chunks = split_text(text, 300)
        self.assertTrue(all(len(chunk) <= 300 for chunk in chunks))
        self.assertEqual('\n'.join(chunks), text)
        self.assertEqual(split_text('short'), ['short'])
        self.assertEqual(len(split_text('x' * 700, 300)), 3)

    def test_error_flags(self):
        self.assertTrue(TelegramError('Forbidden: bot was blocked by the user', 403).is_unreachable_chat)
        self.assertTrue(TelegramError('Bad Request: chat not found', 400).is_unreachable_chat)
        self.assertFalse(TelegramError("Bad Request: can't parse entities", 400).is_unreachable_chat)
        self.assertTrue(TelegramError('Too Many Requests', 429, retry_after=3).is_rate_limited)
