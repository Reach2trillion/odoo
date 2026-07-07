# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Send by Telegram',
    'version': '18.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Send quotations, orders and files via Telegram bot',
    'description': """
Send by Telegram - Instant Business Communication
==================================================

Send sale quotations, purchase orders, and files directly to your customers 
and vendors via Telegram bot. Perfect for businesses that need instant 
communication with their partners.

**Key Features:**

📄 **Document Sharing**
   - Send PDF quotations and purchase orders
   - Attach any files from chatter
   - Images sent with preview (not as documents)

👥 **Group Messaging**  
   - Send to Telegram groups
   - Perfect for B2B communication
   - Dedicated groups per customer/vendor

💬 **Full Integration**
   - Chatter integration with Telegram button
   - All messages logged in Odoo
   - File attachments visible in chatter

🌐 **Multilingual**
   - English, Uzbek, Russian support
   - Messages adapt to user's language

⚡ **Easy to Use**
   - One-click sending from orders
   - Simple bot token configuration
   - Test connection feature

**How to Get Started:**

1. Create a bot via @BotFather on Telegram
2. Add bot token in Settings → General Settings
3. Add Telegram Group IDs to your partners
4. Start sending documents instantly!

**Requirements:**
- Odoo 18.0
- Telegram Bot (free via @BotFather)
- Bot must be admin in target groups
    """,
    'author': 'MRDIL ODOO',
    'support': 'mrdil.odoo@gmail.com',
    'license': 'LGPL-3',
    'price': 22,
    'currency': 'USD',
    'depends': [
        'sale',
        'purchase',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'wizard/telegram_message_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'send_by_telegram/static/src/chatter/chatter_patch.js',
            'send_by_telegram/static/src/chatter/chatter_patch.xml',
        ],
    },
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
