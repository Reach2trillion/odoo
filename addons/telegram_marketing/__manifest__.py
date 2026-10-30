# -*- coding: utf-8 -*-
{
    'name': 'Telegram Marketing & Live Chat',
    'summary': 'Broadcast promotions and announcements to Telegram, and chat with your customers instantly from Odoo',
    'description': """
Telegram Marketing & Live Chat
==============================

* Connect one or several Telegram bots (token from @BotFather).
* Customers press *Start* on your bot and become subscribers (and contacts).
* **Campaigns**: send promotions and announcements to all subscribers, to tagged
  chats, to a custom filter or to a hand-picked list. Personalize with
  placeholders, attach an image or a file, add link buttons, schedule for later
  and follow sent / failed statistics.
* **Inbox**: every private chat, group or channel in one place, with a live
  conversation view and an instant reply box - any chat, any message.
* **Automatic messages**: welcome message on /start, unsubscribe on /stop,
  keyword based auto-replies (any language, e.g. Khmer) and an optional default
  reply.
* Webhook (instant) or polling (no public URL needed) to receive messages.
    """,
    'version': '18.0.1.0.0',
    'category': 'Marketing',
    'author': 'Reach2Trillion',
    'website': 'https://github.com/reach2trillion/odoo',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'contacts'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/telegram_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/telegram_templates.xml',
        'views/telegram_bot_views.xml',
        'views/telegram_chat_tag_views.xml',
        'views/telegram_chat_views.xml',
        'views/telegram_message_views.xml',
        'views/telegram_auto_reply_views.xml',
        'views/telegram_campaign_views.xml',
        'wizard/telegram_compose_views.xml',
        'views/res_partner_views.xml',
        'views/telegram_menus.xml',
    ],
    'demo': [
        'demo/telegram_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'telegram_marketing/static/src/**/*',
        ],
    },
    'application': True,
    'installable': True,
}
