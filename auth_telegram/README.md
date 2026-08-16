# Telegram Login for Odoo 18

Adds a **"Log in with Telegram"** button to the Odoo login page, based on the
official [Telegram Login Widget](https://core.telegram.org/widgets/login).

- **Login**: users whose account is linked to a Telegram account sign in with one click.
- **Sign up**: when *Free sign up* is enabled (Settings → General Settings →
  Customer Account), unknown Telegram accounts automatically get a new (portal)
  user created from the portal template user.
- **Self-service linking**: any logged-in user can link or unlink their own
  Telegram account at `/auth/telegram/link` (protected against login-CSRF with a
  session-bound nonce).
- **Admin linking**: administrators can set a user's *Telegram User ID* on the
  user form (Settings → Users → *Telegram* tab). Users can find their numeric ID
  with Telegram's `@userinfobot`.

## How it works

1. The login page embeds the Telegram Login Widget for your bot.
2. After the user confirms in Telegram, Telegram redirects to
   `/auth/telegram/callback?id=...&auth_date=...&hash=...`.
3. The module verifies the payload exactly as specified by Telegram:
   `hash == HMAC_SHA256(data_check_string, SHA256(bot_token))`, and rejects
   payloads older than 5 minutes.
4. The matching user gets a random **single-use** login token (stored hashed,
   2 minutes validity), which is consumed by a custom `_check_credentials`
   auth method — the same pattern the standard `auth_oauth` module uses.
   Two-factor authentication (TOTP), if enabled for the user, still applies.

No password is ever set or required for Telegram-only users, and Telegram never
shares the bot token with the browser.

## Setup

1. **Create a bot**: talk to [@BotFather](https://t.me/BotFather) in Telegram →
   `/newbot` → note the bot **username** and the **token**.
2. **Register your domain**: still in @BotFather, send `/setdomain`, pick your
   bot, and enter your Odoo domain (e.g. `odoo.example.com`). The widget only
   works on this registered domain, and it must be served over **HTTPS**.
3. **Install this module**: copy the `auth_telegram` folder into your addons
   path, update the apps list, and install *Telegram Login*.
4. **Configure**: Settings → General Settings → *Telegram Authentication* →
   enter the bot username (without `@`) and the bot token, then save.
5. Log out: the login page now shows the Telegram button.
6. Optional: enable **Free sign up** (Settings → General Settings → Customer
   Account → *On invitation / Free sign up*) so new Telegram users can create
   an account on the fly.

## Notes & limitations

- Telegram does not provide e-mail addresses. Auto-created users get their
  Telegram username (or `telegram_<id>`) as login and no e-mail; an
  administrator can complete the record later.
- The *Telegram User ID* is unique per user (enforced by a SQL constraint).
- Tokens sent to the browser are random, single-use, short-lived, and only the
  SHA-256 hash is stored in the database.
- The `auth_date` freshness window is 5 minutes; the login token validity is
  2 minutes (see constants in `models/res_users.py`).
