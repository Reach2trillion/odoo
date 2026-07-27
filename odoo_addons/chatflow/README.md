# ChatFlow – Messenger Marketing Automation for Odoo 18

A ManyChat-style Facebook Messenger bot and marketing tool, as a native
Odoo module. It replaces the standalone `app.py` Flask bot of this
repository with a full Odoo app:

| ManyChat concept | ChatFlow equivalent |
|---|---|
| Connected page | **Configuration → Facebook Pages** |
| Contacts | **Inbox** (subscribers, auto-captured) |
| Flows | **Automation → Flows** (text, voice/TTS, image, quick replies, buttons, actions) |
| Keywords | **Automation → Triggers** |
| Broadcasts | **Marketing → Broadcasts** (tag audiences, scheduling, 24h window) |
| Live chat takeover | Pause Bot + manual **Send Message** on the subscriber |

The Khmer keyword rules from `replies.json` are pre-installed as flows
and triggers (each one sends the Khmer text **and** a Khmer voice
message, exactly like the standalone bot did).

## Installation

1. Copy the `chatflow` folder into your Odoo 18 addons path.
2. (Optional, for voice replies) install gTTS on the Odoo server:
   `pip3 install gtts` — the server also needs outbound internet access.
3. Restart Odoo, update the app list, and install **ChatFlow**.

## Connect your Facebook Page

1. Open **ChatFlow → Configuration → Facebook Pages** and create a page:
   fill in the *Facebook Page ID*, the *Page Access Token* (Meta app →
   Messenger → Access Tokens) and optionally the *App Secret* (enables
   webhook signature checks).
2. Copy the **Webhook URL** and **Verify Token** shown on the form.
3. In the Meta app dashboard (Messenger → Settings → Webhooks), register
   the callback URL with the verify token, and subscribe to
   **messages**, **messaging_postbacks** — and **feed** (Page object) if
   you want automatic comment replies.
4. Click **Setup Get Started Button** on the page form so new
   conversations fire the Welcome trigger.
5. Message your page: the subscriber appears in the Inbox and the bot
   answers with the matching flow.

Your Odoo instance must be reachable from the internet over HTTPS
(`web.base.url` is used to display the webhook URL).

## How it works

- The webhook controller (`/chatflow/webhook`) stores each event and
  returns 200 immediately; a triggered cron processes the queue, so slow
  TTS synthesis can never make Facebook disable the webhook.
- Voice messages are synthesized once per unique text, uploaded to
  Facebook once, and the reusable `attachment_id` is cached in the
  database (`chatflow.attachment.cache`).
- Broadcasts are queued per recipient and sent in batches by a cron;
  progress is visible on the broadcast form.
- If the CRM app is installed, the *Create CRM Lead* flow step creates a
  lead from the conversation.
