from odoo import _, models


class CheckinmeTelegram(models.AbstractModel):
    _inherit = 'checkinme.telegram'

    def _format_checkin_message(self, checkin, *args, **kwargs):
        text = super()._format_checkin_message(checkin, *args, **kwargs)
        event = kwargs.get('event', args[0] if args else 'checkin')
        if event == 'checkin' and checkin._abj_saved_customer_location():
            text += '\n📍 %s' % self._escape(_("The customer had no map location: it was saved from this visit."))
        return text
