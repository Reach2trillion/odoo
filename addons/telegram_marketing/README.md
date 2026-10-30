# Telegram Marketing & Live Chat for Odoo 18 (`telegram_marketing`)

Send **promotions and announcements** to your customers on Telegram and **chat with them
instantly from Odoo** - any chat, any message - with automatic replies for the questions
you get every day.

```
Customer ──► Telegram ──► (webhook or polling) ──► Odoo  Inbox / contacts / auto replies
Odoo  ──► Campaigns, replies, wizard ──► Telegram Bot API ──► customers, groups, channels
```

## Features

| Area | What you get |
|---|---|
| **Campaigns** | Promotions / announcements to *all subscribers*, *subscribers with tags*, a *custom filter* or a *hand-picked list*. Placeholders (`{{ object.first_name ||| there }}`), bold/italic/links, image or file, link buttons, test send, schedule or send now, sent/failed statistics, automatic retry pacing. |
| **Inbox** | Every private chat, group and channel in a kanban with unread badges. Open a chat: live conversation view (refreshes itself when a message arrives), reply box, attachments, *Rich Message* wizard. Message many chats at once from the *Action* menu, or type any `@channel` / chat ID. |
| **Automatic messages** | Welcome message on `/start`, confirmation on `/stop`, keyword auto-reply rules in any language (Khmer, English...), optional default reply. |
| **Customers** | Subscribers become contacts automatically (or are matched by Telegram username / shared phone number). Smart button and *Send Telegram Message* action on contacts. Tags to segment your audience. |
| **Receiving** | Webhook (instant, needs a public HTTPS URL) or polling every minute (works anywhere, even on a laptop). |
| **Safety** | Bot tokens are only visible to Telegram administrators, webhook URLs carry a secret, multi-company rules, rate limiting (Telegram's 30 msg/s), blocked users detected and excluded. |

## Requirements

* Odoo **18.0** (Community or Enterprise) - depends on `base`, `mail`, `contacts`.
* Python `requests` (already required by Odoo).
* For webhook mode: Odoo reachable on a **public HTTPS** address (Telegram only delivers to `https://`).
  Without it, use polling mode.

## Installation

1. Copy `addons/telegram_marketing` into a folder of your Odoo *addons path*
   (with the official Docker image: mount it in `/mnt/extra-addons`, see `docker-compose.odoo.yml`
   at the root of this repository).
2. Restart Odoo, activate developer mode, **Apps ▸ Update Apps List**, search *Telegram* and install
   **Telegram Marketing & Live Chat**.
3. Give your team access: *Settings ▸ Users*, section **Telegram**:
   *User* (inbox, replies, campaigns) or *Administrator* (bots, tokens, auto-reply rules).

## Setup in 5 minutes

### 1. Create the bot
In Telegram, talk to **@BotFather**: `/newbot`, choose a name and a username ending in `bot`.
Copy the token (looks like `123456789:AAH...`). Optional: `/setuserpic`, `/setdescription`.

### 2. Connect it to Odoo
*Telegram ▸ Configuration ▸ Bots ▸ New*: paste the token and click **Check Connection**.
The bot username, the **Start link** and a printable **QR code** appear.

### 3. Choose how messages reach Odoo
* **Webhook (recommended)** - instant. Make sure the system parameter `web.base.url` is your public
  `https://` address (Settings ▸ Technical ▸ System Parameters), then click **Activate Webhook**.
  Odoo registers `https://your-odoo/telegram/webhook/<bot>/<secret>` on Telegram. Behind a reverse
  proxy, start Odoo with `--proxy-mode`. Click **Refresh Webhook Status** to see Telegram's view
  (pending updates, last error).
* **Polling** - no public URL needed. Click **Use Polling Instead**: the scheduled action
  *Telegram: fetch new messages* asks Telegram for new messages every minute.

### 4. Get subscribers
Telegram never lets a bot write first: **a customer must press Start once**. Share the Start link,
print the QR code in your shop and on invoices, post it on Facebook. Add a word after `?start=`
(for example `https://t.me/your_bot?start=shop`) to know where each subscriber came from
(field *Start Parameter* on the chat - filter or tag them later).

Customers unsubscribe with `/stop` and come back with `/start`. People who block the bot are flagged
*Blocked* automatically and skipped by campaigns.

### 5. Automatic messages (bot form ▸ *Automatic Messages*)
* **Welcome message** sent on `/start`, **confirmation** sent on `/stop`.
* **Auto Reply Rules**: keywords (comma separated, any language), match type (*contains*, *equals*,
  *starts with*, *regular expression*), rich reply, optional image/file and link button. Rules are
  tried in order; the first match answers. Use the *Default Reply* when nothing matches, or leave
  it empty so your team answers from the Inbox.
* By default rules only answer in private chats (switch *Auto Reply in Groups* to change that).

## Inbox - any chat, any message

*Telegram ▸ Inbox* lists every conversation, most recent first, with the unread count.

* Open a chat to read the full conversation. The view refreshes by itself when a message arrives
  (Odoo bus) and marks the chat as read.
* Type in the reply box and click **Send**: sent as plain text, exactly as written. Attach a photo
  or a file if needed.
* **Rich Message** (or *Action ▸ Send Telegram Message* on one or several chats / contacts) opens a
  wizard with formatting, placeholders, an image/file and a link button.
  The *Other Chat* field accepts any `@channel`, `@group` or numeric chat ID the bot can reach,
  even if it is not in Odoo yet (the bot must be a member - an administrator for channels).
* Subscribe / unsubscribe, link the chat to a contact, add tags, keep internal notes in the chatter.

## Campaigns

*Telegram ▸ Campaigns ▸ New*

1. **Message**: write it with the editor. Telegram keeps **bold, italic, underline, strikethrough,
   code and links**; headings become bold, lists become `•` lines, other layout becomes text.
   Limits: 4096 characters, 1024 with an image (the module then sends the image first and the text
   as a second message).
2. **Placeholders** (per recipient chat, `object` is the `telegram.chat` record):

   | Placeholder | Result |
   |---|---|
   | `{{ object.first_name ||| there }}` | first name, or *there* when unknown |
   | `{{ object.last_name }}`, `{{ object.username }}` | last name, Telegram username |
   | `{{ object.name }}` | chat name (person or group title) |
   | `{{ object.start_payload }}` | the `?start=` parameter the subscriber came from |
   | `{{ object.partner_id.name }}` | linked contact name (also `.ref`, `.phone`, `.mobile`, `.email`, `.city`, `.commercial_company_name`) |
   | `{{ object.bot_id.name }}`, `{{ object.bot_id.username }}` | your bot |

   The text after `|||` is used when the value is empty. These placeholders work for every Telegram
   user; any other field path or expression (functions, operators) requires the *Mail Template
   Editor* group, which is the standard Odoo rule for dynamic templates.
3. **Image or File** (one per campaign) and **Link Buttons** (shown under the message).
4. **Recipients**: all subscribers, subscribers with tags, a custom filter on chats, or selected chats.
   Tick *Include Groups & Channels* to post in the groups/channels the bot belongs to.
   The *Recipients* counter updates live.
5. **Send Test** to your own chat, then **Send Now** or set a date and **Schedule**.
6. Follow **Statistics** (sent / failed / pending, progress bar) and the *Messages* button.

Sending runs in the scheduled action *Telegram: send queued messages* (every minute, triggered
immediately when you click Send Now). It paces messages to ~25 per second, pauses when Telegram asks
(`429 Too Many Requests`) and processes up to 500 messages per run (system parameter
`telegram_marketing.batch_size`). Failed messages can be retried from the *Messages* list.

## Contacts

* New private chats create a contact automatically (bot option *Create Contacts Automatically*).
  Existing contacts are matched by the **Telegram Username** field, or by phone number when the
  customer shares their contact card in Telegram.
* The contact form shows a **Telegram** smart button and an *Action ▸ Send Telegram Message* entry.

## Scheduled actions and system parameters

| Name | Purpose |
|---|---|
| *Telegram: send queued messages and launch scheduled campaigns* | every minute |
| *Telegram: fetch new messages (bots in polling mode)* | every minute, polling bots only |
| `telegram_marketing.batch_size` | messages sent per cron run (default 500) |
| `telegram_marketing.api_base` | Bot API base URL (default `https://api.telegram.org`), for proxies |

Make sure the cron worker is running (`--max-cron-threads` greater than 0; the Docker image does this
by default).

## Troubleshooting

| Symptom | Check |
|---|---|
| Nothing arrives in webhook mode | Bot form ▸ *Refresh Webhook Status*: Telegram shows the last error. The URL must be `https://` and reachable from the internet; `web.base.url` must be correct; with a reverse proxy use `--proxy-mode`. |
| Polling error `409 Conflict` | A webhook is still registered. The module removes it automatically on the next run; or click *Use Polling Instead* again. |
| `Bad Request: chat not found` | The customer never pressed Start, or the bot is not a member/administrator of the group or channel. |
| `Forbidden: bot was blocked by the user` | The customer blocked the bot; the chat is flagged *Blocked* and skipped. |
| `can't parse entities` | Unbalanced formatting in the message. Use the *Preview* tab to see what Telegram receives. |
| Campaign stuck in *Sending* | The cron is not running, or Telegram asked to slow down (see the *Messages* list for errors). |

## Limitations

* Telegram does not tell bots whether a message was read - statistics show *sent* and *failed* only.
* Files larger than 20 MB sent by customers are not downloaded (Telegram Bot API limit).
* Buttons are link buttons; callback (quiz-style) buttons are not supported.
* Conversations live in the Telegram app, not in Odoo Discuss.

## សង្ខេបជាភាសាខ្មែរ

ម៉ូឌុលនេះភ្ជាប់ Odoo 18 ជាមួយ Telegram Bot របស់អ្នក៖

* **យុទ្ធនាការ (Campaigns)** - ផ្ញើការផ្សព្វផ្សាយ និងសេចក្តីជូនដំណឹងទៅអតិថិជនទាំងអស់ដែលបានចុច Start
  (ឬតាម Tag / តាមការជ្រើសរើស) ជាមួយរូបភាព ប៊ូតុង Link និងការកំណត់ពេលផ្ញើ។
* **ប្រអប់សារ (Inbox)** - មើល និងឆ្លើយតបសារអតិថិជនគ្រប់ Chat ភ្លាមៗពីក្នុង Odoo។
* **សារស្វ័យប្រវត្តិ** - សារស្វាគមន៍ពេល /start, ឆ្លើយតបតាមពាក្យគន្លឹះ (ភាសាខ្មែរ ឬអង់គ្លេស)។
* អតិថិជនត្រូវចុច **Start** លើ Bot មុនសិន ទើប Bot អាចផ្ញើសារទៅពួកគាត់បាន - ចែករំលែក Link ឬ QR Code
  ដែលមាននៅក្នុងទម្រង់ Bot។

## Development

Run the test-suite on a database with the module installed:

```bash
odoo-bin -d <db> --addons-path=<odoo>/addons,<repo>/addons -i telegram_marketing --test-enable --test-tags /telegram_marketing --stop-after-init
```

The tests use an in-memory stand-in for the Telegram API (no network needed).

License: LGPL-3.
