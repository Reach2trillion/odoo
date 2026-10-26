# Checkout: "Use my current location" (abjskincare.com)

A button under the **ទីតាំង-Location** field of the checkout address form
(`/shop/address`). One tap:

1. asks the browser for the customer's GPS position (the phone shows its
   usual permission prompt),
2. looks the position up in OpenStreetMap (Nominatim reverse geocoding),
3. fills **Location** with road, village, commune and district,
   e.g. `ផ្លូវ ២៧១, ភូមិ ៣, សង្កាត់ទួលទំពូងទី ១, ខណ្ឌចំការមន`,
4. selects the **province** (the hidden *city* field follows it, as before:
   view 4665 copies the province name into it),
5. saves the **GPS pin on the customer** when the address is saved
   (`partner_latitude`, `partner_longitude`, `date_localization`).

The customer can still edit everything; the message under the button shows the
full result, a *View on map* link (Google Maps) and *Undo* if it replaced text
they had typed. Khmer pages (`/km/...`) show Khmer only, English pages show
both languages, like the rest of the form. Light and dark (moon) mode are
styled.

## Where the team sees the location

- **Contacts → Map view** and **Inventory → Deliveries → Map view** (Enterprise
  `web_map` is installed): the customer appears at the exact GPS point, and the
  map's *Navigate* button opens Google Maps directions for the driver.
- Contact form → **Partner Assignment** tab → *Geo Location* (Lat / Long and
  the date it was captured).

Don't press *Refresh* / *Compute based on address* there: it replaces the GPS
pin with a geocode of the typed address, which is much less precise in
Cambodia.

## How accurate it is

| Accuracy the phone reports | What the button does |
|---|---|
| up to 300 m (GPS, Wi-Fi) | fills Location and province, saves the pin |
| 300 m to 5 km | only fills the province, if empty; asks the customer to type the address; no pin |
| over 5 km (IP based, e.g. desktop on cable) | changes nothing; asks to turn on GPS or type |

The province comes from the ISO 3166-2:KH code in the lookup result, with the
Khmer and Latin names as a fallback, so all 25 Odoo provinces (codes PNH, KDL,
SRP, ...) are matched whatever language OpenStreetMap answers in.

## Why the pin needs care when saving

- The checkout (`/shop/address/submit`) only writes `res.partner` fields that
  are whitelisted for website forms. `partner_latitude`, `partner_longitude`
  and `date_localization` were whitelisted once with Odoo's own
  `ir.model.fields.formbuilder_whitelist` (run from a one-time scheduled
  action that was deleted afterwards).
- `base_geolocalize` resets the pin to 0 whenever an address is written
  without one, and the checkout writes the whole address on every save. So the
  page re-sends the existing pin as long as Location, province and country are
  unchanged (e.g. the customer only fixed their phone number), and drops it
  when the address changes without a new detection. A detected pin is also
  dropped if the customer then picks a different province or country.
- The hidden inputs only get a `name` (and are only submitted) in those cases;
  an empty named input would overwrite the pin with 0.

## Live objects

| What | Where |
|---|---|
| View | `ir.ui.view` **website_sale.abj_detect_location** (id 5222), QWeb extension of the website copy of `website_sale.address` (id 4573), website *ABJ Skincare*, priority 24 |
| Whitelist | `ir.model.fields` `website_form_blacklisted = False` on `res.partner.partner_latitude`, `partner_longitude`, `date_localization` |

The view's xpaths: after `//input[@id='o_street']` (the box, style and
script) and `data-code` on the province options (`t-att-data-code="s.code"`).
It works alongside the other ABJ checkout views (4575, 4616, 4665, 4953, 5031).

## Changing it

1. Edit `detect_location.js` / `detect_location.css`.
2. `python3 build_arch.py` regenerates `view_arch.xml` (the script and style are
   inlined and XML-escaped; QWeb outputs them unescaped).
3. Run the tests (below).
4. Put the content of `view_arch.xml` into the view's *Architecture*
   (Settings → Technical → User Interface → Views, or through the Odoo MCP
   connection: `update_record` on `ir.ui.view` with `arch_db`).

## Turning it off

- Archive the view (uncheck *Active*): the button disappears immediately and
  the form is exactly as before.
- The whitelist can stay; without the button nothing sends those fields.

## Tests

```bash
cd test
python3 build_fixtures.py /tmp/abj_fixtures      # needs lxml
node test_detect_location.js /tmp/abj_fixtures /tmp/abj_shots   # needs playwright
```

`build_fixtures.py` rebuilds the live form from `test/live_views/` (the arch of
view 4573 and the ABJ views extending it, copied from the site) plus this view,
renders it with a small QWeb subset and a stand-in for Odoo's `address.js`.
The Node tests emulate GPS fixes and answer the Nominatim requests with canned
responses: Phnom Penh, Kandal without ISO code, English names, all 25 provinces
by ISO code and by Khmer name, rough fixes, permission denied, outside
Cambodia, lookup failures, keeping or dropping an existing pin, province
reload after a country change, Khmer page, dark-mode colours, screenshots.

If you change the other checkout views on the site, refresh
`test/live_views/` so the tests keep matching the real form.

## Limits

- It detects where the phone **is**. Customers ordering from work for home
  delivery should type the address instead; the message tells them to check it.
- OpenStreetMap is very good for provinces, districts and communes in Cambodia
  and good for Phnom Penh streets; house numbers are rare, so the message asks
  the customer to add theirs.
- In-app browsers (Facebook, Messenger, Telegram) usually allow location; if
  one blocks it the customer gets a clear message and types the address.
- Nominatim is a free service with a fair-use policy (at most about one
  request per second for the whole site; it is only called when a customer
  taps the button) and requires the "© OpenStreetMap" credit shown under the
  result.
