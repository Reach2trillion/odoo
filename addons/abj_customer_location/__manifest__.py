{
    'name': 'Customer Map Location',
    'version': '18.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Save where a customer is: paste the Google Maps link they sent on Telegram, '
               'or tap a button on the delivery when you arrive',
    'description': """
Customer Map Location
=====================

Every customer (and every delivery address) gets a **Map location** on its contact form:

* **Office** - paste what the customer sent on Telegram / Messenger: a Google Maps link
  (``maps.app.goo.gl/...`` share links included), an Apple Maps / Waze / OpenStreetMap link or
  coordinates (``11.5564, 104.9282``). The location is read from it when you save.
* **Delivery** - the delivery order shows *No map location for this customer yet* and an
  **I'm here: save customer location** button. Tapped at the customer's door, it saves the
  phone's GPS position. When a location already exists, it checks it and asks before
  replacing a location that is far away.
* **Sale Check** - with the Sale Check app installed, a visit checked in at a customer
  without a location saves it (bridge module *Customer Map Location - Sale Check*).

Safety rules: GPS positions less precise than 50 m are refused, so are positions taken at the
company or warehouse address, a location far from the saved one is only replaced after a
confirmation, and every change is written in the chatter (who, when, from where, previous
location). Changing the address no longer erases the map location (standard Odoo resets it).

The location is stored in the standard Geo Latitude / Geo Longitude fields, so the Map view,
Sale Check distance checks and every report using them work with it.
""",
    'author': 'ABJ SkinCare',
    'license': 'LGPL-3',
    'depends': ['base_geolocalize', 'mail', 'stock'],
    'data': [
        'views/res_partner_views.xml',
        'views/stock_picking_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'abj_customer_location/static/src/**/*',
        ],
    },
    'installable': True,
    'application': False,
}
