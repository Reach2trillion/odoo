# Customer Map Location (`abj_customer_location`)

Odoo 18 module. Saves **where a customer is**, in the standard *Geo Latitude / Geo Longitude*
fields of the contact, in two ways:

| Who | Where | What they do |
|---|---|---|
| Office | Contact form, **Map location** (under the address) | Paste what the customer sent on Telegram: a Google Maps link (`maps.app.goo.gl/...` share links included), an Apple Maps / Waze / OpenStreetMap link, or coordinates such as `11.5564, 104.9282`. Save. |
| Delivery person | Delivery order (Inventory › Deliveries), on the phone | The order shows **No map location for this customer yet**. At the customer's door, tap **I'm here: save customer location**. |
| Salesperson | Sale Check / ABJ app | Check in at a customer without a location: the visit saves it (bridge module `abj_customer_location_checkin`, installed automatically with Sale Check). |

## On the phone

| Who | Where | What happens |
|---|---|---|
| Salesperson or delivery person with the **ABJ app** (or the *Install on phone* web app) | *Check In Now* › customer › *Delivery* (or any visit type) › *Check In* | A customer without a map location gets the check-in position. The result screen says **Customer location saved** and the managers' Telegram message adds *it was saved from this visit*. A customer who already has a location is never changed from the app. |
| Delivery person in **Odoo** (Chrome / Safari, or the Odoo app) | Inventory › Deliveries › the order | Yellow box with **I'm here: save customer location**; once saved, **Navigate with Google Maps**. |
| Anyone who received the customer's link on Telegram | Telegram: touch and hold the link › *Copy*. Odoo: the customer › *Map location* › paste › *Save* | Same as on a computer. |

A customer created in the ABJ app (*New customer*) gets the phone position, except when the phone
is at the company or warehouse address: then the first visit at the customer saves it.

The ABJ app itself has no field to paste a link and no button to replace a wrong location (its
screens belong to the Sale Check module): use the customer or check-in form in Odoo for that.

Phone checklist: open Odoo with its `https://` address, switch on Location (GPS), and allow
location for the browser / ABJ app / Odoo app when asked. If it was refused once: phone
*Settings › Apps › (Chrome, ABJ or Odoo) › Permissions › Location › Allow*.

## Checking a saved location

When the customer already has a location, the delivery button **checks** it instead:
within 100 m it only says *You are at the saved location*. Further away, it asks *Replace the
saved location with where you are now?* before changing anything. Once saved, the delivery
order shows **Navigate with Google Maps**.

## Safety rules

* GPS positions less precise than **50 m** are refused (phone indoors, or located by the phone
  network). The person is asked to wait outside a few seconds and tap again.
* A GPS position within **150 m of the company or warehouse address** is refused: it was taken
  at the office, not at the customer. *Set the map location of the company (ABJ SkinCare) and of
  the warehouse contact (Stock Office) first, otherwise this check cannot work.*
* A saved location is **never replaced silently**: the GPS button asks first, Sale Check
  visits only fill a missing location.
* Every change is written in the contact's chatter: new location (link to the map), source
  (pasted link, phone GPS with accuracy, Sale Check visit, typed in, computed from the address),
  the delivery or visit it came from, who, and the previous location.
* **Changing the address no longer erases the location.** Standard Odoo (`base_geolocalize`)
  resets the location to nothing whenever the street, city, province, ZIP or country is
  written. This module keeps it and writes a note in the chatter when the address really
  changed (*if the customer moved, save the new location*).
* A pasted link is only opened by the server when it is a Google link without coordinates
  (short share links): no other web address is ever contacted.

## Pasting a link: what works

| Pasted | Result |
|---|---|
| `https://maps.app.goo.gl/...` (Google Maps *Share* button, phone or computer) | The server opens the link and reads the pin. Needs internet access from the Odoo server. |
| `https://www.google.com/maps/place/.../@11.55,104.92,17z/data=...!3d11.5563!4d104.9282` | The pin (`!3d`/`!4d`), not the centre of the screen. |
| `https://maps.google.com/?q=11.5564,104.9282` (Telegram location opened in a browser) | Read directly. |
| `11.5564, 104.9282` / `11°33'23.0"N 104°55'41.6"E` / `11.5564° N, 104.9282° E` | Read directly (at least 4 decimals: 3 decimals is 110 m, another street). |
| Apple Maps (`ll=`, `coordinate=`), Waze (`ll=`, `to=ll.`), OpenStreetMap, `geo:` | Read directly. |
| A link to a search or a list of places | Refused, with what to do instead. |

If a short link cannot be read (no internet on the server, Google changed its pages), the
message explains how to copy the coordinates by hand: on a computer, right-click the place in
Google Maps and click the numbers at the top; on a phone, touch and hold the place, the numbers
appear in the search box.

## Settings

System parameters (*Settings › Technical › System Parameters*, developer mode):

| Key | Default | Meaning |
|---|---|---|
| `abj_customer_location.max_accuracy_m` | `50` | Least precise GPS position accepted (m) |
| `abj_customer_location.same_place_m` | `100` | A GPS position this close to the saved location confirms it (m) |
| `abj_customer_location.office_radius_m` | `150` | GPS positions this close to the company / warehouse address are refused (m); `0` disables the check |

## Lists and filters

* Contacts: filters **No map location** / **Has map location** (ask the customers without a
  location to send their pin on Telegram).
* Transfers: filter **Customer without map location**.

## Delivery addresses

A customer with several places (shop, home, warehouse) should have one **Delivery Address**
contact per place (*Contacts & Addresses* tab): each has its own **Map location**, and the
delivery button saves the location of the delivery address of the order, not of the main
contact.

## Technical notes

* `tools/location.py`: link and coordinate reader, plain Python, unit tested with recorded
  Google answers (the test server has no internet access).
* `res.partner`: `abj_location_paste` (non-stored, read in `create`/`write`), source / accuracy
  / user / date of the location, `abj_action_save_gps_location` (contact form button),
  address-change protection in `write`.
* `stock.picking`: `abj_action_save_arrival_location` (delivery button); the delivery person
  needs no right on contacts (the location is written with `sudo`, the chatter keeps the real
  author).
* Web: one OWL view widget, `<widget name="abj_location_gps" method="..." string="..."/>`.
* The browser GPS needs HTTPS (it works on the Odoo website address, not on a plain `http://IP`).
* Sale Check bridge (`abj_customer_location_checkin`): the first visit at a customer without a
  location now saves it, so that visit shows *Verified On Site (0 m)* (as for customers created
  on the phone today). Three Sale Check tests assume a visit leaves such a customer without a
  location (`test_location_status_unknown_and_no_gps`,
  `test_location_status_follows_customer_geolocation`,
  `test_search_customers_nearby_recent_and_query`): they fail when the bridge is installed,
  by design. Run Sale Check's tests without the bridge, or update those three tests.

Run the tests:

```bash
odoo-bin -d test_db --addons-path=<odoo>/addons,<this repo>/addons,<o8o repo> \
  -i checkinme_sales_activity,abj_customer_location --test-enable \
  --test-tags /abj_customer_location,/abj_customer_location_checkin --stop-after-init
```
