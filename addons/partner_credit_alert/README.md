# Customer Credit Alerts (`partner_credit_alert`) — Odoo 18

Odoo's built-in *Sales Credit Limit* only shows a passive yellow banner on a quotation or
invoice when the customer is already over the limit. This module turns the credit limit
into a managed process:

| Capability | Details |
|---|---|
| Two alert levels | **Approaching Limit** at a configurable % of the limit (default 80 %), **Limit Exceeded** above 100 %. |
| Alert records | `credit.alert` with lifecycle *Open → Acknowledged → Resolved*, chatter, review activities, snapshot of the credit position, link to the triggering document. |
| Notifications | Salesperson of the customer + a list of *Credit Controllers* (Invoicing > Settings) are notified and get a *Credit Review* activity. Optional e-mail to the customer when the limit is exceeded. |
| Policy | *Warn only* or *Block*: blocking refuses confirmation of sales orders and posting of customer invoices that push the customer over the limit. Set per company, overridable per customer. |
| Override | Members of the **Credit Manager** group (accounting administrators by default) tick *Credit Override* + reason on the document; the override is logged in the chatter. |
| Credit hold | Managers can put a customer *On Credit Hold* to block all new sales regardless of the balance. |
| Live status | On the customer: exposure, available credit, usage %, status badge, smart button to alerts; filters *Approaching / Over Credit Limit / On Credit Hold* in the customer list. Red / orange banners on quotations and invoices. |
| Automatic re-evaluation | On sales order confirmation, invoice / credit note / payment posting, reset to draft, credit limit or policy change, plus a daily scheduled check. Alerts resolve themselves when the customer is back within the limit. |
| Snooze | Resolving an alert manually while the customer is still over the threshold snoozes new alerts of the same level for N days (default 7). |

Exposure = **Total Receivable** (unpaid posted receivable balance) + **confirmed sales orders not
yet invoiced**, exactly the figures Odoo uses for its own credit warning.

## Installation

1. Copy `addons/partner_credit_alert` into your addons path (or add this `addons` folder to
   `addons_path`).
2. Update the apps list and install **Customer Credit Alerts**.
3. Invoicing > Settings > *Sales Credit Limit*: enable it and set the default limit, the warning
   threshold, the policy and the credit controllers.
4. On a customer, Invoicing tab > *Credit Limits*: set the partner limit; the *Credit Alerts* group
   underneath shows the live position and the per-customer policy / hold.

Depends on `account`, `sale`, `mail`.

## Security

| Group | Rights |
|---|---|
| Sales / Invoicing users | See alerts, acknowledge, resolve, add notes. |
| Credit Manager (`partner_credit_alert.group_credit_alert_manager`) | Everything above + override blocks, set / release credit hold, re-open alerts. Implied by *Accounting / Administrator*. |

Alerts are company-specific (multi-company record rule).

## Technical notes

* `res.partner._credit_alert_evaluate()` is the single place that computes limit, exposure and
  level; `_credit_alert_check()` creates / escalates / resolves alerts and is called from every hook.
* Blocking is enforced in `sale.order.action_confirm()` and `account.move._post()`; pass
  `credit_alert_skip_check=True` in context to bypass it from custom code (imports, migrations).
* The native `partner_credit_warning` banner is hidden on the sales order and invoice forms and
  replaced by the module's banners (it would otherwise duplicate the message).

## Tests

```
odoo-bin -d <db> -i partner_credit_alert --test-enable --test-tags /partner_credit_alert --stop-after-init
```
