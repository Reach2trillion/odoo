{
    'name': 'Journal Access Restriction',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Hide selected journals, and everything booked in them, from chosen users',
    'description': """
Journal Access Restriction
==========================

Adds a **Hidden From Users** field on each journal
(Accounting > Configuration > Journals > *journal* > Advanced Settings > Control-Access).

Users listed there can no longer see that journal, or anything booked in it:

* the journal itself (dashboard, journal pickers, payment registration)
* journal entries and bank statement lines
* journal items, and therefore the accounting reports they feed
* payments
* bank statements
* analytic items coming from those journal items

Accounting Administrators always see every journal, so an administrator
cannot lock themselves out.
""",
    'author': 'ABJ SkinCare',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'security/journal_access_security.xml',
        'views/account_journal_views.xml',
    ],
    'installable': True,
    'application': False,
}
