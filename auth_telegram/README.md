# Telegram Login for Odoo 18

Adds a **"Log in with Telegram"** button to the Odoo login page, with three
login methods (Settings → General Settings → *Telegram Authentication*):

| Method | How the customer logs in | Setup needed |
|---|---|---|
| **Telegram chat** (recommended) | Taps the button → Telegram opens on your bot → taps **Start** → taps **✅ Yes, Login** → signed in (optionally types a one-time code shown by the bot) | bot token + username, public https URL |
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
Website                      Telegram bot chat                       Website tab
"Log in with Telegram"  ──►  /start <token> (sent automatically)
   (page polls status)       🔐 Authentication Request
                             App / Account / Username / Device / IP
                             [✅ Yes, Login] [❌ Cancel]
                             ✅ Login Successful! Welcome, X!
                             👈 Go back to the website            ──►  signed in, redirected
                             📱 Share phone number? (optional)

With "One-time code" enabled, after Yes:
                             ✅ Confirmed! Your one-time code: 123456
                             👈 Type it on the website            ──►  type code → signed in
                             ✅ Login Successful! (+ phone request)
```

1. The website creates a short-lived login request (10 minutes) and shows a
   waiting page with an **Open Telegram** button (and a QR code on desktop).
   The request token is kept in the browser session and in the Telegram deep
   link only, never in a URL the browser requests. The page polls the request
   status every 2 seconds.
2. Telegram opens your bot with `/start <token>`; the bot (via webhook) sends
   the **Authentication Request** message, showing the device and IP address
   the request came from, with Yes / Cancel buttons. Only the Telegram user who
   sent `/start` can answer; if a second Telegram account opens the same link
   (e.g. a photographed QR code) the request is cancelled and both are told.
3. On **Yes**, the bot resolves (or creates) the Odoo user, marks the request
   confirmed and sends **Login Successful** (or, with *One-time code*, the code
   to type on the website).
4. The website tab that started the request completes the login automatically
   (after the one-time code, when enabled). Only that browser session can
   complete it, exactly once; afterwards the request is spent. Users with
   two-factor authentication are sent to the TOTP step like after a password
   login.
5. Optionally the bot then asks the customer to **share their phone number**
   (one tap, Telegram's `request_contact`), which is saved on the user and
   contact. Because the customer pressed Start, the bot can now message them
   (used by the `telegram_notification` module).

Messages are bilingual English / Khmer; edit the `MSG_*` constants in
`models/telegram_bot.py` to change them.

### One-time code (recommended)

With *One-time code* enabled in Settings, the bot sends a six-digit code
**after** the customer taps Yes, and the website where the login was started
asks for it (three attempts, then the request is cancelled and both the website
and the Telegram chat say so). The code is never sent to the browser. Someone who sends a
customer their own login link ("open this and tap Yes") therefore still cannot
get in: the code only appears in the customer's Telegram, together with a
warning never to share it, and only the attacker's browser could use it. This
also prevents accidental approvals.

No login method is phishing-resistant against a customer who follows an
attacker's instructions and hands the code over; the bot's warning and the
device / IP shown in every prompt are what remains. Without the one-time code,
a customer who taps Yes on a link somebody else sent them approves that
person's login. The setting is frozen per request when the request is created.

### Linking from an existing account

Logged-in users link / unlink Telegram at `/auth/telegram/link`. Because this
adds or removes a way to sign in, users who have a password must re-enter it
first (valid for 10 minutes, like Odoo's own identity check); accounts without
a password (created by the Telegram sign up) must log in with their currently
linked Telegram account again (same 10 minute window), so an unattended
logged-in browser cannot be used to take over the account. An account with
neither a password nor a linked Telegram account (a user signed in through
another SSO module, or whose link an administrator removed) has nothing to
confirm with and cannot link one from this page: the user sets a password
first (the page offers the password reset when it is available) or asks an
administrator to link the account. The Telegram
account that was linked before is notified when it is unlinked or replaced.
An account that can only sign in with Telegram (no password, and no e-mail
address or the public password reset disabled) cannot be unlinked, only
switched to another Telegram account.

### Setup (chat login)

1. Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`) and note
   its **username** and **token**.
2. Make sure Odoo's `web.base.url` is your public **https** address (Settings →
   Technical → System Parameters). Telegram calls
   `https://yourdomain/auth/telegram/webhook`. When Odoo runs behind a reverse
   proxy (Docker, nginx, Traefik, Caddy...), run Odoo with `proxy_mode = True`
   and have the proxy forward `X-Forwarded-For`, `X-Forwarded-Proto` **and**
   `X-Forwarded-Host` (Odoo only honours these headers when `proxy_mode` is on
   and `X-Forwarded-Host` is present). Without this, the *Authentication
   Request* message cannot show the customer's IP address (the module detects
   the situation, shows `-` and logs a warning rather than showing the proxy's
   address). Also set `web.base.url.freeze` to `True`, otherwise Odoo rewrites
   `web.base.url` from an internal address at each administrator login.
3. Settings → General Settings → *Telegram Authentication*: choose
   **Telegram chat**, enter the bot username and token, save. The webhook is
   registered automatically; the *Status* line shows the result (use *Check
   Status* / *Register Webhook* if needed). The "Log in with Telegram" button
   only appears once the webhook is registered.
4. Optional: enable **One-time code** and **Free sign up** (so new customers
   get an account on the fly).

Upgrading from a version before 3.0 keeps your current method (OpenID Connect
or the legacy widget); switch to **Telegram chat** in Settings when ready. The
*Status* line must read "Registered: https://yourdomain/auth/telegram/webhook";
"Not registered here" means Telegram delivers this bot's updates to another
server (a staging copy, an old domain): save again to re-register.

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
2. In Odoo: Settings → General Settings → *Telegram Authentication* → select
   **OpenID Connect** as Login Method, paste the Client ID and Client Secret.
   Keep the **Bot Username** and **Bot Token** filled in too — they are used
   by the Telegram notifications module and by the chat login.
3. Log out: the login page shows the "Log in with Telegram" button.
4. Optional: enable **Free sign up** so new Telegram users get an account
   automatically.

## Which method is used

The **Login Method** selected in Settings is used as long as it is fully
configured: *Telegram chat* needs the bot username, bot token and a webhook
registered on this server's URL; *OpenID Connect* needs the Client ID and
Client Secret; the *Legacy Login Widget* needs the bot username and token. If
the selected method is not complete (the webhook registration failed, the
Client ID/Secret were cleared...), the module falls back to the other complete
non-deprecated method (OpenID Connect or Telegram chat); when none is complete
the "Log in with Telegram" button is hidden. For the *Telegram chat* method the
*Status* line in Settings reports the webhook registration (a webhook refused
by Telegram is also logged on the server); a missing Bot Username, Bot Token,
Client ID or Client Secret simply hides the button without a message, so check
that those fields are filled in for the selected method. The
legacy widget is never used as a fallback: it only runs when it is the selected
method (chosen in Settings, or selected by the upgrade from a version before
3.0 for databases that only had a bot configured), and its callback only
accepts payloads requested by the same browser session. A failed *Check
Status* without a usable answer from Telegram (unreachable, rate limited, a
Telegram-side error) does not hide the chat login: the registration is kept
and the failed check is shown after it. When Telegram answers that the request
itself is refused (Unauthorized / Not Found: a wrong or revoked bot token), the
chat login is hidden until the token is fixed and the settings are saved
again.

## Notes

- The phone number is only stored when the user shares it: with the chat
  login by tapping the bot's *Share phone number* button (optional, can be
  switched off in Settings), with OpenID Connect by consenting on Telegram's
  authorization screen. The legacy widget never provides it. Users may decline
  and still log in.
- The *Telegram User ID* is unique per user (SQL constraint).
- Login tokens sent to the browser are random, single-use, short-lived, and
  only their SHA-256 hash is stored.
- Bot API errors are logged without the bot token (connection errors from the
  HTTP library would otherwise include it).
