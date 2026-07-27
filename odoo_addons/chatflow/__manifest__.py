# -*- coding: utf-8 -*-
{
    'name': 'ChatFlow – Messenger Marketing Automation',
    'summary': 'ManyChat-style Facebook Messenger bot: flows, keyword triggers, '
               'subscribers, tags, broadcasts and Khmer voice (TTS) replies.',
    'description': """
ChatFlow – Messenger Marketing for Odoo
=======================================
A ManyChat-style chatbot and marketing automation module:

* Connect one or several Facebook Pages (Messenger webhook built in)
* Capture every person who messages the page as a Subscriber
* Build multi-step Flows: text, voice (text-to-speech, e.g. Khmer),
  images, quick replies, button templates and actions
  (add/remove tag, create CRM lead, human handoff)
* Keyword Triggers, Welcome trigger (Get Started) and Default reply
* Auto-reply to comments on Page posts
* Tag-based Broadcasts with scheduling and 24h-window compliance
* Full conversation inbox with manual replies and bot pause

Voice replies require the optional ``gtts`` python package
(``pip3 install gtts``) and outbound internet access.
    """,
    'category': 'Marketing',
    'version': '18.0.1.0.0',
    'author': 'ABJ',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'mail'],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/chatflow_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'data/chatflow_data.xml',
        'views/chatflow_page_views.xml',
        'views/chatflow_subscriber_views.xml',
        'views/chatflow_flow_views.xml',
        'views/chatflow_trigger_views.xml',
        'views/chatflow_broadcast_views.xml',
        'views/chatflow_message_views.xml',
        'wizard/send_message_views.xml',
        'views/chatflow_menus.xml',
    ],
    'application': True,
    'installable': True,
}
