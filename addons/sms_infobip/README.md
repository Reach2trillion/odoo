# Infobip SMS Connector for Odoo 18 (`sms_infobip`)

Send every SMS from Odoo through your own [Infobip](https://www.infobip.com/sms/api)
account instead of the Odoo IAP SMS service. Built for businesses in **Cambodia
(+855)** — where you want your own registered sender ID and direct operator routes
(Smart, Cellcard, Metfone) — but works for any country Infobip covers.

The connector plugs into the standard Odoo 18 SMS framework, so it transparently
covers **everything** that sends SMS:

- **CRM** — text a lead/customer from the chatter, SMS activities, automation rules
- **SMS Marketing** (`mass_mailing_sms`) — mass campaigns with per-recipient delivery tracking
- Contacts, Sales, Inventory, server actions, SMS templates, ...

## Features

- Official Infobip HTTP API: `POST {base_url}/sms/2/text/advanced`, batched (up to 500 SMS per request)
- **Delivery reports**: Infobip pushes the final status back to Odoo — messages show as
  *Delivered* / *Sent* / *Failed* with the operator's reason, in the chatter and in
  SMS Marketing statistics
- **Custom sender ID** (alphanumeric, e.g. your brand name)
- **Local number normalization**: `012 345 678` automatically becomes `85512345678`
  (default prefix configurable, `855` out of the box)
- **Send Test SMS** wizard in the settings
- Clean fallback: disable the toggle and Odoo instantly uses the IAP service again
- Errors are mapped to Odoo's standard failure types (insufficient credit, wrong
  number format, sender not registered, ...) so resend/failure flows keep working

## Compatibility

All Odoo **18.0** builds — both recent ones (with the pluggable `SmsApiBase`
provider framework) and earlier 18.0 releases (e.g. Debian/nightly packages)
where the IAP client is hardcoded in `sms.sms._send()`. The module detects the
framework at runtime and uses the matching integration path.

## Installation

1. Copy `addons/sms_infobip` into an addons path of your Odoo 18 server.
2. Restart Odoo and update the apps list (*Apps > Update Apps List*).
3. Install **Infobip SMS Connector**.

Dependencies: the standard `sms` module (auto-installed with CRM) and the Python
`requests` library (ships with Odoo).

## Configuration

1. Create an account on [portal.infobip.com](https://portal.infobip.com).
   The portal homepage shows your personal **API base URL**
   (`https://xxxxx.api.infobip.com`) and lets you create an **API key**.
2. In Odoo, open **Settings > Infobip SMS**:
   - Enable **Send SMS via Infobip**
   - Paste the **API Base URL** and **API Key**
   - Set your **Sender ID** (3–11 alphanumeric characters, e.g. `MyBrand`)
   - Keep **Default Country Prefix** = `855` for Cambodia
   - Leave **Delivery Reports** enabled if your Odoo is reachable from the internet
3. **Save**, then click **Send Test SMS** and text yourself.

### Cambodia notes

- Register your alphanumeric sender ID with Infobip for the Cambodian operators —
  unregistered senders may be replaced or filtered. Your Infobip account manager or
  the portal's *Sender registration* flow handles Smart, Cellcard and Metfone.
- Free-trial Infobip accounts can only message the phone number you verified at
  signup; the connector surfaces this as an "Unregistered Account" error.
- Khmer (Unicode) message bodies are supported; note that Unicode SMS segments are
  70 characters instead of 160, which affects per-message cost.

### Delivery reports

The connector asks Infobip (per message, via `notifyUrl`) to POST the final status to:

```
https://<your-odoo-domain>/sms_infobip/status/<secret-token>
```

The URL (including its auto-generated secret token) is shown in the settings — you
can also configure it globally on your Infobip API key as a fallback. If your Odoo
is not publicly reachable, messages simply stay in the *Sent* state.

## How it works (technical)

- `tools/sms_api_infobip.py` — `SmsApiInfobip(SmsApiBase)`: implements
  `_send_sms_batch()` using the Infobip API, sets each destination's `messageId`
  to the `sms.sms` UUID so responses and webhooks map 1-to-1 to Odoo records, and
  maps Infobip statuses/error groups to Odoo failure types.
- `models/res_company.py` — `_get_sms_api_class()` returns the Infobip class when enabled.
- `models/sms_sms.py` — `_split_by_api()` routes queued/batch sends through Infobip.
- `controllers/main.py` — token-protected webhook that updates `sms.tracker`
  records (chatter notifications, mailing traces) exactly like the core IAP
  `/sms/status` controller.
- Config lives in `ir.config_parameter` (`sms_infobip.*`), editable in Settings.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "Infobip rejected the API Key" | Wrong key or base URL — copy both from the portal homepage |
| "Unregistered Account" on a trial | Trial accounts only reach the verified number; upgrade or verify the destination |
| "Sender not allowed" / sender replaced | Register your sender ID for the destination country in the Infobip portal |
| Messages stay "Sent", never "Delivered" | Odoo not reachable from the internet, or delivery reports disabled |
| Nothing sent, SMS in error "Server Error" | Check the Odoo server log — the Infobip response is logged |

Run the test suite with:

```
odoo-bin -d <db> --test-tags /sms_infobip --stop-after-init
```

## License

LGPL-3.
