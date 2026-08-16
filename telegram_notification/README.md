# Telegram Notifications for Odoo 18

Companion module to **Telegram Login** (`auth_telegram`). Sends Telegram
messages to customers whose Odoo account is linked to a Telegram account.

## What gets sent

| Event | Trigger | Message |
|---|---|---|
| Quotation | Quotation marked as sent | 📄 quotation name, total, portal link |
| Order | Sales order confirmed | ✅ order name, total, portal link |
| Delivery | Outgoing transfer validated | 📦 order reference + carrier tracking ref/link when available |
| Invoice | Customer invoice posted | 🧾 invoice name, total, portal link |

Each event can be switched on/off in Settings → General Settings →
*Telegram Authentication*.

The customer's Telegram username also appears on the contact form
(clickable `t.me/...` link) so your team can reach out manually — useful
when there is a problem with an order.

## Who can receive messages

Telegram only lets a bot message people who allowed it:

- customers who ticked **"Allow ... to message me"** when they used the
  Telegram login button (the button requests this by default), or
- customers who opened your bot and pressed **Start**.

Anyone else is silently skipped (a warning is logged). Messages are sent
after the database transaction commits and never block or roll back the
business flow if Telegram is unreachable.

## About phone numbers

The Telegram Login Widget shares only: Telegram ID, name, username and
photo. **Telegram never shares the user's phone number through login** —
keep collecting the phone at checkout if you need it.
