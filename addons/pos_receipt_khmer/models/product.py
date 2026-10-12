import re
from collections import defaultdict

from odoo import _, api, fields, models

# Khmer (U+1780-U+17FF) and Khmer Symbols (U+19E0-U+19FF)
KH_CHARS = re.compile('[\u1780-\u17ff\u19e0-\u19ff]')
# a token that the fill helper keeps after the first Khmer word: Latin letters and Western or Khmer
# digits, with inner or trailing + - . / % ("BB", "SPF50+", "100ml", "៥០ml", "3-in-1")
LATIN_TOKEN = re.compile(r'[A-Za-z0-9\u17e0-\u17e9][A-Za-z0-9\u17e0-\u17e9+\-./%]*')
# invisible characters a Khmer typist may leave around a word (ZWSP, ZWNJ, ZWJ, BOM)
INVISIBLE = '\u200b\u200c\u200d\ufeff'
# punctuation that ends the name phrase when it ends a word ("ក្រែម, BB ..." -> "ក្រែម"): ASCII and
# Khmer (khan, bariyoosan, colon, beyyal, ...), not the repetition sign ៗ (part of its word)
TRAILING_PUNCT = re.compile('[,.;:!?\u2026\u17d4\u17d5\u17d6\u17d8\u17d9\u17da]+$')


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    kh_receipt_name = fields.Char(
        string='Khmer name (receipt)',
        help='Khmer product name printed on the POS receipt (e.g. "ឡេការពារកម្តៅថ្ងៃ"). Empty: the Khmer '
             '(km_KH) translation of the product name when there is one, else only the product name. '
             'Point of Sale > Settings > Bills & Receipts > Product names on the receipt chooses how '
             'it is printed; reload the POS to apply a change.')

    # ------------------------------------------------------------------------------------------
    # Fill helper: "Khmer receipt name: fill from Sales Description" (server action)
    # ------------------------------------------------------------------------------------------
    @api.model
    def _kh_name_from_description(self, text):
        """Khmer receipt name taken from a Sales Description, or '' when it does not start with a
        Khmer word: the first whitespace-separated word, plus the Latin / digit words that directly
        follow it ("ក្រែម BB ស្តើងស្រាល ..." -> "ក្រែម BB"). Punctuation at the end of a word ends the
        name and is not kept ("ក្រែម, BB" -> "ក្រែម", "ក្រែម BB, ស្តើង" -> "ក្រែម BB"). Any white space
        separates words, no-break spaces included (text pasted from the web often has them between
        every word)."""
        tokens = [token.strip(INVISIBLE) for token in (text or '').split()]
        tokens = [token for token in tokens if token]
        if not tokens:
            return ''
        first = TRAILING_PUNCT.sub('', tokens[0]).strip(INVISIBLE)
        if not KH_CHARS.search(first):
            return ''
        words = [first]
        if first == tokens[0]:
            for token in tokens[1:]:
                word = TRAILING_PUNCT.sub('', token)
                if not word or not LATIN_TOKEN.fullmatch(word):
                    break
                words.append(word)
                if word != token:
                    break
        return ' '.join(words)

    def _kh_fill_receipt_name(self):
        """Set the Khmer receipt name of the products that have none from their Sales Description.
        Never overwrites a name. Returns (filled products, [(product, reason), ...] skipped).
        The Sales Description is translatable: its Khmer (km_KH) value is tried first when Khmer is
        an active language (it falls back to the en_US value when it has no translation), then the
        value in the user's language, so the result does not depend on who runs the action."""
        langs = []
        if 'km_KH' in dict(self.env['res.lang'].get_installed()):
            langs.append('km_KH')
        if self.env.lang not in langs:
            langs.append(self.env.lang)
        # one batch read per language
        descriptions = [
            self.with_context(lang=lang).mapped(lambda t: t.description_sale or '') for lang in langs
        ]
        skipped = []
        to_write = defaultdict(list)
        for i, template in enumerate(self):
            if (template.kh_receipt_name or '').strip():
                skipped.append((template, _('already has a Khmer name')))
                continue
            texts = [values[i] for values in descriptions if values[i].strip()]
            if not texts:
                skipped.append((template, _('no Sales Description')))
                continue
            name = next(filter(None, map(self._kh_name_from_description, texts)), '')
            if not name:
                skipped.append((template, _('the Sales Description does not start with a Khmer word')))
                continue
            to_write[name].append(template.id)
        filled = self.browse()
        for name, ids in to_write.items():
            templates = self.browse(ids)
            templates.write({'kh_receipt_name': name})
            filled |= templates
        return filled, skipped

    def action_kh_fill_receipt_name(self):
        filled, skipped = self._kh_fill_receipt_name()
        message = self.env._('%(count)s product(s) filled.', count=len(filled))
        if skipped:
            # one group per reason: "already has a Khmer name: A, B; no Sales Description: C"
            by_reason = defaultdict(list)
            for template, reason in skipped:
                by_reason[reason].append(template.display_name)
            max_listed = 20
            groups = []
            for reason, names in by_reason.items():
                listed = ', '.join(names[:max_listed])
                if len(names) > max_listed:
                    listed = self.env._('%(list)s and %(count)s more', list=listed, count=len(names) - max_listed)
                groups.append(self.env._('%(reason)s (%(count)s): %(list)s', reason=reason, count=len(names), list=listed))
            message = self.env._(
                '%(filled)s Skipped %(count)s, %(groups)s.', filled=message, count=len(skipped), groups='; '.join(groups),
            )
        action = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._('Khmer receipt name'),
                'message': message,
                'type': 'success' if filled and not skipped else 'warning' if skipped else 'info',
                'sticky': bool(skipped),
            },
        }
        if filled:
            # show the new names in the list / form the action was started from
            action['params']['next'] = {'type': 'ir.actions.client', 'tag': 'soft_reload'}
        return action

    # ------------------------------------------------------------------------------------------
    # Khmer translation of the name (fallback of the receipt name)
    # ------------------------------------------------------------------------------------------
    def _kh_km_name_translations(self):
        """{template id: Khmer (km_KH) translation of the name} for the templates whose km_KH name is
        real Khmer: km_KH is an active language, the translation differs from the en_US name and
        contains Khmer characters. Two queries for the whole recordset (one per language)."""
        if not self or 'km_KH' not in dict(self.env['res.lang'].get_installed()):
            return {}
        en_names = self.with_context(lang='en_US').mapped('name')
        km_names = self.with_context(lang='km_KH').mapped('name')
        result = {}
        for template, en_name, km_name in zip(self, en_names, km_names):
            km_name = (km_name or '').strip()
            if km_name and km_name != (en_name or '').strip() and KH_CHARS.search(km_name):
                result[template.id] = km_name
        return result


class ProductProduct(models.Model):
    _inherit = 'product.product'

    kh_pos_name_km = fields.Char(
        string='Khmer name on the POS receipt',
        compute='_compute_kh_pos_names',
        help='What the POS prints as the Khmer name: the Khmer name (receipt) of the product, else '
             'the Khmer (km_KH) translation of its name, else nothing.')
    kh_pos_name_en = fields.Char(
        string='English name on the POS receipt',
        compute='_compute_kh_pos_names',
        help='The English (en_US) name of a product that has a Khmer name, with its variant values and '
             'without the internal reference: printed under the Khmer name ("Khmer + English") whatever '
             'the language of the cashier, whose POS loads the product names in that language.')

    @api.depends('kh_receipt_name', 'name', 'product_template_attribute_value_ids')
    def _compute_kh_pos_names(self):
        # batch: the translations of every template without a receipt name in two queries
        missing = self.product_tmpl_id.filtered(lambda t: not (t.kh_receipt_name or '').strip())
        translations = missing._kh_km_name_translations()
        for product in self:
            product.kh_pos_name_km = (
                (product.kh_receipt_name or '').strip()
                or translations.get(product.product_tmpl_id.id, '')
            )
        # the en_US display name (as the POS loads it: no [internal reference]) of the products that
        # have a Khmer name, in one batch; new records (no id yet) keep their own display name
        named = self.filtered(lambda p: p.kh_pos_name_km and isinstance(p.id, int))
        en_names = dict(zip(named.ids, named.with_context(
            lang='en_US', display_default_code=False, partner_id=False, seller_id=False,
        ).mapped('display_name')))
        for product in self:
            if not product.kh_pos_name_km:
                product.kh_pos_name_en = ''
            else:
                product.kh_pos_name_en = en_names.get(product.id) or product.display_name or ''

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        # [] would mean "all fields" (not what core returns for products): nothing to add then
        return fields_list + ['kh_pos_name_km', 'kh_pos_name_en'] if fields_list else fields_list
