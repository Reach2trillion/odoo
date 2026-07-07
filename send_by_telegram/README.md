# Send by Telegram - Odoo 18 Module

📱 Send quotations and purchase orders directly to your customers via Telegram!

## Features

- ✅ Send Sale Quotations via Telegram
- ✅ Send Purchase Orders via Telegram
- ✅ Send messages from Chatter with file attachments
- ✅ Images sent with preview (not as documents)
- ✅ PDF documents automatically generated
- ✅ Full chatter integration with attachment history
- ✅ Multilingual support (Uzbek, Russian, English)
- ✅ Automatic "Quotation Sent" status update

## Installation

1. Copy `send_by_telegram` folder to your Odoo addons path
2. Update Apps List in Odoo
3. Install "Send by Telegram" module

## Configuration

### 1. Create Telegram Bot
1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command
3. Follow instructions to create your bot
4. Copy the bot token

### 2. Configure in Odoo
1. Go to **Settings → General Settings**
2. Find **Send by Telegram** section
3. Enter your bot token
4. Click **Test Bot** to verify connection

### 3. Add Group IDs to Partners
1. Go to **Contacts**
2. Open a partner record
3. Add **Telegram Group ID** (e.g., `-1001234567890`)

> **Note:** Your bot must be added as an admin to the Telegram group!

## Usage

### From Sales/Purchase Orders
1. Open a quotation or purchase order
2. Click **Send by Telegram** button
3. Review the message
4. Check "Attach PDF Report" if needed
5. Click **Send**

### From Chatter
1. Open any record with chatter (Sale Order, Purchase Order, etc.)
2. Click **Telegram** button in chatter
3. Write your message
4. Attach files if needed (images will be sent with preview)
5. Click **Send**

## Technical Details

- **Odoo Version:** 18.0
- **License:** LGPL-3
- **Dependencies:** `sale`, `purchase`, `mail`
- **Languages:** English, Uzbek, Russian

## Support

For support, please contact: your-email@company.com

## Changelog

### Version 18.0.1.0.0
- Initial release
- Sale/Purchase order integration
- Chatter integration with file attachments
- Image preview support
- Multilingual messages
