{
    'name': 'Customer Map Location - Sale Check',
    'version': '18.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'A Sale Check visit or delivery at a customer without a map location saves it',
    'description': """
Customer Map Location - Sale Check
==================================

Installed automatically with *Customer Map Location* when the Sale Check app is installed.

* Checking in at a customer who has no map location yet (any activity type that counts as a
  field visit: visit, delivery, payment collection...) saves the check-in GPS position as the
  customer's map location, when the GPS is precise enough (50 m by default) and the position
  is not the company / warehouse address.
* A customer who already has a map location is never changed automatically: a check-in far
  from it shows *Far From Customer*, and the check-in form offers **Replace the customer's map
  location with this position** (asks for a confirmation first).
* The phone screen (ABJ app) shows **Customer location saved** instead of *Verified On Site*
  for the visit that saved it, and the managers' Telegram message says so.
* Customers created from the phone screen get the phone position as their location, except
  when the phone is at the company / warehouse address (customer created from the office).
""",
    'author': 'ABJ SkinCare',
    'license': 'LGPL-3',
    'depends': ['abj_customer_location', 'checkinme_sales_activity'],
    'data': [
        'views/checkinme_checkin_views.xml',
    ],
    'installable': True,
    'auto_install': True,
    'application': False,
}
