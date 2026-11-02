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
| Payment | Online payment confirmed | ✅ amount, order/invoice, portal link (to the customer) |
| Payment alert | Online payment confirmed | 💰 amount, customer (name, @telegram, phone), order, provider, backend link (to the director / staff) |

Each event can be switched on/off in Settings → General Settings →
*Telegram Authentication*.

### Director / staff alerts

Payment alerts are sent to:

- every Odoo user with **Telegram Payment Alerts** ticked on their user form
  (Settings → Users → *Telegram* tab) — the user must be linked to Telegram and
  have allowed the bot to message them (or pressed Start on the bot);
- the **Extra Alert Chat IDs** from the settings: comma-separated Telegram chat
  IDs, e.g. the director's personal chat or a management group. For a group,
  add the bot to the group and use the group's (negative) ID.

The customer's Telegram username also appears on the contact form
(clickable `t.me/...` link) so your team can reach out manually — useful
when there is a problem with an order.

## Who can receive messages

Telegram only lets a bot message people who allowed it:

- customers who signed in or linked their account with the **Telegram chat**
  login: they pressed **Start** on your bot, so the bot can always message them;
- customers who signed in with **OpenID Connect** and accepted the "allow the
  bot to message you" consent on Telegram's authorization page;
- customers who ticked **"Allow ... to message me"** on the legacy Login
  Widget (requested by default);
- anyone who opened your bot and pressed **Start**.

Anyone else is silently skipped (a warning is logged). Messages are sent
after the database transaction commits and never block or roll back the
business flow if Telegram is unreachable.

## About phone numbers

After a **Telegram chat** login or link, the bot asks the customer to share
their phone number with one tap (Settings → *Ask for phone number after
login*, on by default, only when the contact has no phone yet). The
**OpenID Connect** login includes the phone number when the customer
consents. The number is stored on the user (*Telegram Phone*) and copied to
the contact's phone field when that is empty, and is shown in the staff
payment alert. The legacy Login Widget shares only Telegram ID, name,
username and photo, never the phone number: with that method, keep
collecting the phone at checkout if you need it.
