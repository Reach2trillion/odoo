# COD Delivery Alert via Telegram + Shipping Label (`sale_cod_telegram_alert`)

Odoo 18 module for ABJ. It answers one question for the delivery driver:
**"Do I collect money for this parcel, and how much?"**

## The problem it solves

Today nobody records, at order time, whether a customer will pay the driver
in cash or has already paid (ABA QR, bank transfer, credit customer). The
invoice and the payment are only created *after* the delivery is validated,
so the packing message and the shipping label cannot say anything about
cash. The driver has to guess or call the office.

No module can *detect* this automatically because the information does not
exist anywhere in Odoo. This module therefore adds the missing input first,
then pushes it to the driver through the two channels they already use.

## What it adds

### 1. "Delivery Payment" on every sales order (the input)

| Value | Meaning for the driver |
|---|---|
| **Cash on Delivery** (default) | collect cash: *Amount to Collect* (defaults to the order total, editable for deposits) |
| **Already Paid** | do not collect anything |
| **Pay Later / Credit** | do not collect anything, the customer settles later |

Plus a free-text **Driver Note (COD)** ("customer pays in KHR", "call
before delivery", ...). A default value can be set per customer (Contact >
Sales & Purchase > *Default Delivery Payment*), useful for credit shops.

The value is mirrored on the delivery order (form, list, filters, group by)
with a red **COD** ribbon, so the office sees it at a glance.

### 2. Telegram alert to the delivery group (the digital channel)

Sent with the same bot as *Send by Telegram*, to the same group as the
*Delivery Packing Telegram Notification* module by default, so it lands
right under the packing message:

```
💵 COD - ប្រមូលប្រាក់ពីអតិថិជន
COLLECT CASH: $ 23.00

🧾 S00649 | 🚚 SO/OUT/00448
👤 Xue Xuan
📞 012 345 678
📍 St. 271, Toul Tompoung, Phnom Penh
🛒 Order total: $ 23.00
📝 Customer pays in KHR
🧑‍💼 Kim Sreypich
```

Already paid / credit orders are announced too (`✅ PAID - DO NOT collect
money`, `🕓 PAY LATER - DO NOT collect money at delivery`) so the absence of
a COD message is never ambiguous. Optional: only alert COD orders.

When it is sent (Settings > COD Delivery Alert):

* when the sales order is confirmed (default, same moment as the packing
  message), and/or
* when the delivery order is validated (`🚚 Out for delivery`),
* an `⚠️ UPDATED` alert whenever the payment type, the amount to collect,
  the note or the order lines change after the first alert,
* manually with the **Telegram COD Alert** button on the sales order and
  on the delivery order.

Every send (or failure) is logged in the chatter. A Telegram outage never
blocks order confirmation or delivery validation.

### 3. COD block on the 80x100mm shipping label (the physical channel)

The existing *Shipping Label* report of the `stock_shipping_label` module
gets a bold, colour-coded one-line block under the address:

* red **COD - ប្រមូលប្រាក់** with the amount to collect on the right,
* green **PAID - បង់រួចហើយ - NO CASH**,
* orange **PAY LATER - បង់ពេលក្រោយ - NO CASH**,

followed by the driver note in small type. The three texts are editable in
the settings, and the block can be switched off.

The label is already full with a 4-line address, so when the block is
printed the surrounding spacing is tightened slightly to keep everything on
one 80x100mm page. Keep the driver note to one line.

## Installation

1. Copy `addons/sale_cod_telegram_alert` into the server's addons path.
2. Apps > Update Apps List > install **COD Delivery Alert via Telegram +
   Shipping Label**.
3. Settings > COD Delivery Alert: leave *Telegram Chat ID* empty to reuse
   the packing group, or set another group. The bot token of *Send by
   Telegram* is reused automatically.

Dependencies: `sale_stock`, `stock_shipping_label` (the 80x100mm label).
`send_by_telegram` and `delivery_packing_telegram` are read as fallbacks
for the bot token and chat ID but are not required.

## Limitations / notes

* Existing confirmed orders get *Cash on Delivery* by default when the
  module is installed (the compute runs on install); review the ones that
  are actually paid or on credit before printing labels for them.
* The amount to collect is reset to the order total whenever order lines
  change. Edit it after the lines are final.
* The alert is sent synchronously (10 s timeout) like the packing message.
