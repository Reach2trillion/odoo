# Telegram Login for Odoo 18

Adds a **"Log in with Telegram"** button to the Odoo login page, using
Telegram's **OpenID Connect** login (the current flow — the old Login Widget
is deprecated), with the legacy widget still supported as a fallback.

- **Login**: users whose account is linked to a Telegram account sign in with one click.
- **Sign up**: when *Free sign up* is enabled (Settings → General Settings →
  Customer Account), unknown Telegram accounts automatically get a new (portal)
  user created from the portal template user.
- **Phone number**: with the OIDC flow, Telegram can share the user's verified
  phone number (with their consent). It is stored on the user (*Telegram
  Phone*) and copied to the contact's phone field when that is empty.
- **Bot messaging consent**: the login requests `telegram:bot_access`, so your
  bot may message the user afterwards (used by the `telegram_notification`
  module).
- **Self-service linking**: any logged-in user can link or unlink their own
  Telegram account at `/auth/telegram/link`.
- **Admin linking**: administrators can set a user's *Telegram User ID* on the
  user form (Settings → Users → *Telegram* tab).

## How the OIDC flow works

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

## Setup

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
