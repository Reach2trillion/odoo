# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import models


def post_init_hook(env):
    """Create the Cambodian taxes for every existing Cambodian company."""
    companies = env['res.company'].search([])
    companies._l10n_kh_create_taxes()
