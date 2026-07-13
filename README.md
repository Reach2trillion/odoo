# Facebook Auto-Reply Bot — Khmer Voice 🇰🇭🔊

A small Dockerized service that automatically answers your Facebook Page:

- **Messenger messages** → replies with **Khmer text + a Khmer voice (audio) message**, generated with text-to-speech.
- **Comments on Page posts** → replies with a Khmer text comment.

When someone asks about **ABJ** (products, price, location, delivery…), the bot matches
keywords from `replies.json` and answers automatically in Khmer.

## How it works

```
Facebook user ──▶ Facebook webhook ──▶ this bot (Flask, port 8000)
                                          │  1. match keywords in replies.json
                                          │  2. text-to-speech (Khmer, gTTS)
                                          ◀─ 3. send text + voice via Send API
```

Voice files are cached and each unique reply is uploaded to Facebook only once
(the reusable `attachment_id` is stored in a Docker volume), so repeated replies are fast.

## 1. Prerequisites

- Docker + Docker Compose
- A Facebook **Page** and a Meta **app** (https://developers.facebook.com) with the
  **Messenger** product added
- A public HTTPS URL to this server (a domain with reverse proxy, or `ngrok http 8000` for testing)

## 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:

| Variable | Description |
|---|---|
| `PAGE_ACCESS_TOKEN` | Page token from *Meta app → Messenger → Access Tokens* |
| `VERIFY_TOKEN` | Any secret string you invent; used once when registering the webhook |
| `APP_SECRET` | *App settings → Basic → App Secret* (optional, enables signature checks) |
| `TTS_LANG` | Voice language, `km` = Khmer (default) |
| `SEND_TEXT_WITH_VOICE` | `true` = send text and voice, `false` = voice only |
| `REPLY_TO_COMMENTS` | `true` = also auto-reply to comments on Page posts |

Edit **`replies.json`** to change the answers — each rule is a list of keywords
(English and/or Khmer) plus the Khmer reply that will be spoken. `default_reply`
is used when nothing matches.

## 3. Run with Docker

```bash
docker compose up -d --build
docker compose logs -f
```

Health check: `curl http://localhost:8000/` → `{"status": "ok", ...}`

## 4. Connect the webhook to Facebook

1. In the Meta app go to **Messenger → Settings → Webhooks → Add Callback URL**.
2. Callback URL: `https://YOUR-DOMAIN/webhook` — Verify token: the `VERIFY_TOKEN` from `.env`.
3. Subscribe the webhook to the fields: **`messages`**, **`messaging_postbacks`**
   (and **`feed`** under the *Page* object if you want comment auto-replies).
4. Under **Access Tokens**, connect your Page and generate the `PAGE_ACCESS_TOKEN`.
5. Send your Page a message — you should get a Khmer text + voice reply within seconds.

> While the app is in Development mode only app admins/testers get replies.
> Switch the app to Live mode (requires `pages_messaging` permission approval)
> so every customer gets auto-replies.

## Khmer summary — សង្ខេបជាភាសាខ្មែរ

កម្មវិធីនេះឆ្លើយតបសារ Facebook Page ដោយស្វ័យប្រវត្តិ។ ពេលអតិថិជនសួរអំពី ABJ
វានឹងផ្ញើសារជាអក្សរខ្មែរ រួមទាំង **សារជាសំឡេងខ្មែរ** ទៅកាន់ពួកគាត់វិញភ្លាមៗ។
អ្នកអាចកែសម្រួលចម្លើយនៅក្នុងឯកសារ `replies.json` បានតាមចិត្ត។

## Customizing replies

`replies.json`:

```json
{
  "rules": [
    {
      "name": "price",
      "keywords": ["price", "តម្លៃ"],
      "reply": "សម្រាប់តម្លៃផលិតផល ABJ សូមទុកសារ..."
    }
  ],
  "default_reply": "អរគុណសម្រាប់សាររបស់អ្នក!"
}
```

Keywords are matched case-insensitively as substrings of the incoming message.
The file is re-read on every message, so edits apply without a rebuild.

## Troubleshooting

- **No reply received** — check `docker compose logs -f`; verify the webhook shows
  as *Complete* in the Meta dashboard and the Page is subscribed to `messages`.
- **`(#10) This message is sent outside of allowed window`** — Facebook only allows
  replies within 24 h of the user's last message; this bot always replies immediately,
  so this normally only appears during manual API testing.
- **Voice fails but text works** — the container needs outbound internet access to
  `translate.google.com` for text-to-speech.
