# Telegram Login for Odoo 18

Adds a **"Log in with Telegram"** button to the Odoo login page, with three
login methods (Settings → General Settings → *Telegram Authentication*):

| Method | How the customer logs in | Setup needed |
|---|---|---|
| **Telegram chat** (recommended) | Taps the button → Telegram opens on your bot → taps **Start** → taps **✅ Yes, Login** → signed in | bot token + username, public https URL |
| OpenID Connect | Telegram's authorization page | BotFather OIDC client ID/secret, redirect URI |
| Legacy Login Widget | Telegram widget (deprecated by Telegram) | `/setdomain` in BotFather |

Common to all methods:

- **Login**: users whose account is linked to a Telegram account sign in with one click.
- **Sign up**: when *Free sign up* is enabled (Settings → General Settings →
  Customer Account), unknown Telegram accounts automatically get a new (portal)
  user created from the portal template user.
- **Profile photo** becomes the user's avatar (never overwriting a manually
  uploaded one), the contact gets a **"Telegram" tag**, and the Telegram
  username is stored on the user.
- **Self-service linking**: any logged-in user can link or unlink their own
  Telegram account at `/auth/telegram/link`.
- **Admin linking**: administrators can set a user's *Telegram User ID* on the
  user form (Settings → Users → *Telegram* tab).

## Telegram chat login

```
Website                      Telegram bot chat                     Website tab
"Log in with Telegram"  ──►  /start <token> (sent automatically)
   (page polls status)       🔐 Authentication Request
                             App / Account / Username
                             [✅ Yes, Login] [❌ Cancel]
                             ✅ Login Successful! Welcome, X!
                             [🚀 Open App Automatically]    ──►  signed in, redirected
                             📱 Share phone number? (optional)
```

1. The website creates a short-lived login request (10 minutes) and shows a
   waiting page with an **Open Telegram** button (and a QR code on desktop).
   The page polls the request status every 2 seconds.
2. Telegram opens your bot with `/start <token>`; the bot (via webhook) sends
   the **Authentication Request** message with Yes / Cancel buttons. Only the
   Telegram user who sent `/start` can answer them.
3. On **Yes**, the bot resolves (or creates) the Odoo user, marks the request
   confirmed and sends **Login Successful** with an **Open App** button.
4. The polling tab completes the login automatically; the Open App button does
   the same from Telegram's in-app browser. A confirmed request can be
   completed at most twice and only within its validity.
5. Optionally the bot then asks the customer to **share their phone number**
   (one tap, Telegram's `request_contact`), which is saved on the user and
   contact. Because the customer pressed Start, the bot can now message them
   (used by the `telegram_notification` module).

Messages are bilingual English / Khmer; edit the `MSG_*` constants in
`models/telegram_bot.py` to change them.

### Setup (chat login)

1. Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`) and note
   its **username** and **token**.
2. Make sure Odoo's `web.base.url` is your public **https** address (Settings →
   Technical → System Parameters). Telegram calls
   `https://yourdomain/auth/telegram/webhook`.
3. Settings → General Settings → *Telegram Authentication*: choose
   **Telegram chat**, enter the bot username and token, save. The webhook is
   registered automatically; the *Status* line shows the result (use *Check
   Status* / *Register Webhook* if needed).
4. Optional: enable **Free sign up** so new customers get an account on the fly.

Note: a bot uses either a webhook or long polling — if another program polls
this bot with `getUpdates`, the webhook will conflict with it.

## OpenID Connect flow


1. The login button starts a standard OpenID Connect **authorization code flow
   with PKCE** at `https://oauth.telegram.org/auth` (state + nonce bound to the
   session).
2. Telegram redirects back to `/auth/telegram/callback?code=...&state=...`.
3. Odoo exchanges the code at `https://oauth.telegram.org/token`
   (HTTP Basic auth with your Client ID / Client Secret + PKCE verifier) and
   validates the returned `id_token` claims (issuer, audience, expiry, nonce).
4. The matching user gets a random **single-use** login token (stored hashed,
   2 minutes validity), consumed by a custom `_check_credentials` auth method —
   the same pattern as the standard `auth_oauth` module. TOTP 2FA still applies.

### Setup (OpenID Connect)

1. In **@BotFather**: open your bot → *Web Login* settings → **Switch to
   OpenID Connect Login** (⚠️ this permanently disables the old widget flow
   for the bot). Then:
   - register the **Redirect URI**: `https://yourdomain.com/auth/telegram/callback`
   - register your domain as **Trusted Origin**: `https://yourdomain.com`
   - copy the **Client ID** and **Client Secret**.
2. In Odoo: Settings → General Settings → *Telegram Authentication* → paste
   the Client ID and Client Secret. Keep the **Bot Token** filled in too — it
   is used by the Telegram notifications module (and by the legacy widget
   fallback).
3. Log out: the login page shows the "Log in with Telegram" button.
4. Optional: enable **Free sign up** so new Telegram users get an account
   automatically.

If the Client ID/Secret are left empty but a bot username + token are set, the
module falls back to the legacy Login Widget flow (only works for bots that
have never been switched to OIDC).

## Notes

- Telegram shares the phone number only if the user consents on the Telegram
  authorization screen; users may decline and still log in.
- The *Telegram User ID* is unique per user (SQL constraint).
- Login tokens sent to the browser are random, single-use, short-lived, and
  only their SHA-256 hash is stored.
