#!/usr/bin/env python3
"""Render test pages of the live /shop/address form with the new view applied.

live_views/ holds the arch_db of the website copy of website_sale.address
(4573) and the ABJ views that extend it, as they are on abjskincare.com. They
are combined in Odoo's order (priority, then id), the new arch is applied last,
and the result is rendered with a small QWeb subset into one HTML page per
scenario. Odoo's address.js is replaced by a stand-in that reloads the
provinces on country change the same way and records the submitted FormData.

    python3 build_fixtures.py OUT_DIR
"""
import copy
import html
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace as NS

from lxml import etree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from build_arch import build  # noqa: E402

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

# (view id, priority) of the live extensions of view 4573
LIVE_EXTENSIONS = [(4575, 16), (4593, 16), (4616, 16), (4665, 16), (4953, 20)]
NEW_VIEW = (10 ** 6, 24)


# -- view inheritance ---------------------------------------------------------

def locate(arch, spec):
    if spec.tag == 'xpath':
        nodes = arch.xpath(spec.get('expr'))
    else:
        attrs = {k: v for k, v in spec.attrib.items() if k not in ('position', 'version')}
        nodes = [n for n in arch.iter(spec.tag) if all(n.get(k) == v for k, v in attrs.items())]
    if not nodes:
        raise ValueError('cannot locate %s' % etree.tostring(spec)[:160])
    return nodes[0]


def apply_spec(arch, spec):
    node = locate(arch, spec)
    position = spec.get('position', 'inside')
    if position == 'attributes':
        for attribute in spec.iterchildren('attribute'):
            if (attribute.text or '').strip():
                node.set(attribute.get('name'), attribute.text)
            else:
                node.attrib.pop(attribute.get('name'), None)
        return
    new = []
    for child in spec.iterchildren():
        if not isinstance(child.tag, str):
            continue
        if child.tag == 'xpath' and child.get('position') == 'move':
            moved = locate(arch, child)
            moved.getparent().remove(moved)
            moved.tail = None
            new.append(moved)
        else:
            new.append(copy.deepcopy(child))
    if position == 'inside':
        for n in new:
            node.append(n)
    elif position == 'after':
        ref = node
        for n in new:
            ref.addnext(n)
            ref = n
    elif position == 'before':
        for n in new:
            node.addprevious(n)
    elif position == 'replace':
        for n in new:
            node.addprevious(n)
        node.getparent().remove(node)
    else:
        raise ValueError(position)


def combined_arch(with_new_view=True):
    arch = etree.fromstring((HERE / 'live_views' / 'view_4573.xml').read_bytes())
    views = [(prio, vid, (HERE / 'live_views' / ('view_%d.xml' % vid)).read_text()) for vid, prio in LIVE_EXTENSIONS]
    if with_new_view:
        views.append((NEW_VIEW[1], NEW_VIEW[0], build()))
    for _prio, _vid, text in sorted(views):
        ext = etree.fromstring(text.encode('utf-8'))
        for spec in (ext.iterchildren() if ext.tag == 'data' else [ext]):
            if isinstance(spec.tag, str):
                apply_spec(arch, spec)
    return arch


# -- QWeb subset ----------------------------------------------------------------

class QWeb:
    """Enough QWeb for this template: t-if/elif/else, t-foreach, t-set,
    t-esc/t-out, t-att-*, t-attf-*, groups; t-call renders website.layout's
    body inline and skips everything else. Template text is output raw, as
    Odoo does (so inline scripts get their real `&&` and `<`)."""

    def ev(self, expr, ctx):
        return eval(expr.strip(), {'__builtins__': {}}, ctx)  # noqa: S307 - test fixture

    def render(self, el, ctx):
        if 't-foreach' in el.attrib:
            out = []
            for item in self.ev(el.get('t-foreach'), ctx):
                sub = dict(ctx)
                sub[el.get('t-as')] = item
                out.append(self.one(el, sub))
            return ''.join(out)
        return self.one(el, ctx)

    def one(self, el, ctx):
        a = el.attrib
        if 't-set' in a:
            ctx[a['t-set']] = self.ev(a['t-value'], ctx) if 't-value' in a else self.children(el, dict(ctx))
            return ''
        if 'groups' in a and not a['groups'].startswith('!'):
            return ''
        if 't-call' in a:
            return self.children(el, ctx) if a['t-call'] == 'website.layout' else ''
        inner = None
        if 't-esc' in a or 't-out' in a:
            value = self.ev(a.get('t-esc') or a.get('t-out'), ctx)
            inner = '' if value is None or value is False else html.escape(str(value))
        if el.tag == 't':
            return inner if inner is not None else self.children(el, ctx)
        attrs = []
        for k, v in a.items():
            if k.startswith('t-att-'):
                value = self.ev(v, ctx)
                if value is None or value is False:
                    continue
                attrs.append((k[6:], k[6:] if value is True else str(value)))
            elif k.startswith('t-attf-'):
                attrs.append((k[7:], re.sub(r'\{\{(.+?)\}\}|#\{(.+?)\}',
                                            lambda m: str(self.ev(m.group(1) or m.group(2), ctx)), v)))
            elif not k.startswith('t-') and k != 'groups':
                attrs.append((k, v))
        start = '<%s%s' % (el.tag, ''.join(' %s="%s"' % (k, html.escape(v, quote=True)) for k, v in attrs))
        if el.tag in VOID:
            return start + '/>'
        return start + '>' + (inner if inner is not None else self.children(el, ctx)) + '</%s>' % el.tag

    def children(self, el, ctx):
        out = [el.text or '']
        taken = None
        for child in el:
            if not isinstance(child.tag, str):  # comments
                out.append(child.tail or '')
                continue
            a = child.attrib
            if 't-if' in a:
                taken = bool(self.ev(a['t-if'], ctx))
                if taken:
                    out.append(self.render(child, ctx))
            elif 't-elif' in a:
                if taken is False:
                    taken = bool(self.ev(a['t-elif'], ctx))
                    if taken:
                        out.append(self.render(child, ctx))
            elif 't-else' in a:
                if taken is False:
                    out.append(self.render(child, ctx))
                taken = None
            else:
                taken = None
                out.append(self.render(child, ctx))
            out.append(child.tail or '')
        return ''.join(out)


# -- scenarios -----------------------------------------------------------------------

class NoPartner:
    """partner_sudo for a new address: an empty, falsy recordset."""

    def __bool__(self):
        return False

    def __getattr__(self, name):
        return 0.0 if name in ('partner_latitude', 'partner_longitude') else False


STATES = [NS(id=s[0], name=s[1], code=s[2]) for s in json.loads((HERE / 'states_kh.json').read_text())]
KH = NS(id=116, code='KH', name='Cambodia')
COUNTRIES = [NS(id=217, code='TH', name='Thailand'), KH, NS(id=233, code='US', name='United States')]


def customer(**values):
    base = dict(name='Sok Reach', email='sok@example.com', phone='0873188999', street='21A 170',
                street2=False, city='រាជធានីភ្នំពេញ',
                zip=False, vat=False, commercial_company_name=False,
                partner_latitude=0.0, partner_longitude=0.0, date_localization=False)
    base.update(values)
    return NS(**base)


def context(partner, country, state_id=False, anonymous=False):
    return {
        'website': NS(account_on_checkout='optional', _display_partner_b2b_fields=lambda: False,
                      has_google_places_api_key=lambda: False),
        'res_company': NS(country_id=KH),
        'request': NS(csrf_token=lambda: 'csrf-test'),
        'is_anonymous_cart': anonymous,
        'use_delivery_as_billing': True,
        'address_type': 'delivery',
        'only_services': False,
        'partner_sudo': partner,
        'partner_id': getattr(partner, 'id', False) if partner else False,
        'country': country or NS(id=False, code=False, name=False),
        'countries': COUNTRIES,
        'country_states': STATES if country is KH else [],
        'state_id': state_id,
        'zip_before_city': False,
        'show_vat': False,
        'discard_url': '/shop/checkout',
        'callback': '',
    }


SCENARIOS = {
    # logged-in customer editing an address that already has a GPS pin
    'existing_pin': (context(customer(id=7, partner_latitude=11.5621, partner_longitude=104.916,
                                      date_localization='2026-10-01'), KH, 1777), 'en-US'),
    # same customer, no pin yet
    'existing': (context(customer(id=7), KH, 1777), 'en-US'),
    # logged-in customer adding a new delivery address, country preset (GeoIP)
    'new_kh': (context(NoPartner(), KH), 'en-US'),
    # anonymous cart without a country: view 4575 picks Cambodia, Odoo reloads the provinces
    'anon_nocountry': (context(NoPartner(), None, anonymous=True), 'en-US'),
    # Khmer version of the site
    'new_kh_km': (context(NoPartner(), KH), 'km-KH'),
}

PAGE = """<!DOCTYPE html>
<html lang="{lang}"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Address | ABJ Skincare (test replica)</title>
<style>{theme}</style></head>
<body class="{body_class}"><div id="wrapwrap"><main>{content}</main></div>
<script>{odoo_stub}</script>
</body></html>"""

# rough stand-in for the live theme (glass views 4862 / 5020) so screenshots are meaningful
THEME = """
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans Khmer","Khmer OS",sans-serif;
background:linear-gradient(135deg,#dff3fb,#eef6fb 50%,#e6f0f8);color:#1f2a33;min-height:100vh}
.container{max-width:1140px;margin:0 auto;padding:16px;box-sizing:border-box}
.row{display:flex;flex-wrap:wrap;margin:0 -8px}.row>*{padding:0 8px;box-sizing:border-box;width:100%}
@media(min-width:992px){.col-lg-8{width:66.66%}.col-lg-6{width:50%}}
h3{font-weight:400;font-size:2rem;margin:.5rem 0 1rem}
.col-form-label{display:block;padding:10px 0 6px}
.form-control,.form-select{display:block;width:100%;box-sizing:border-box;padding:11px 14px;font:inherit;
background:rgba(255,255,255,.94);border:1px solid rgba(31,42,51,.12);border-radius:14px;color:#1f2a33;appearance:none}
.alert{border-radius:10px;padding:8px 12px}.alert-info{background:#d6eef4;border:1px solid #b6dde8;color:#245766}
.small{font-size:.875rem}.mt-2{margin-top:.5rem}.mb-2{margin-bottom:.5rem}.mb-0{margin-bottom:0}
.btn{display:inline-flex;align-items:center;justify-content:center;border-radius:999px;padding:11px 22px;font-weight:600;
border:1px solid transparent;text-decoration:none;font-size:1rem;cursor:pointer}
.btn-primary{background:#000;color:#fff}.btn-outline-secondary{background:#fff;color:#1f2a33;border-color:rgba(0,0,0,.08)}
.d-flex{display:flex}.flex-column{flex-direction:column}.align-items-center{align-items:center}
.justify-content-between{justify-content:space-between}.d-md-none{display:none}.w-100{width:100%}.mt32{margin-top:32px}
@media(min-width:768px){.flex-md-row{flex-direction:row}.w-md-auto{width:auto}}
.text-danger{color:#b91c1c}.text-muted{color:#64748b}
body.abjgl-lite{background:radial-gradient(120% 80% at 20% 0%,#171C22 0%,#0C0F12 55%,#0A0C0F 100%);color:#ECEAE4}
body.abjgl-lite #wrapwrap#wrapwrap#wrapwrap#wrapwrap,
body.abjgl-lite #wrapwrap#wrapwrap#wrapwrap#wrapwrap h3,body.abjgl-lite #wrapwrap#wrapwrap#wrapwrap#wrapwrap p,
body.abjgl-lite #wrapwrap#wrapwrap#wrapwrap#wrapwrap span,body.abjgl-lite #wrapwrap#wrapwrap#wrapwrap#wrapwrap a,
body.abjgl-lite #wrapwrap#wrapwrap#wrapwrap#wrapwrap label{color:#ECEAE4!important;-webkit-text-fill-color:#ECEAE4!important}
body.abjgl-lite #wrapwrap#wrapwrap#wrapwrap#wrapwrap .form-control,
body.abjgl-lite #wrapwrap#wrapwrap#wrapwrap#wrapwrap .form-select{background:rgba(255,255,255,.07)!important;
border-color:rgba(255,255,255,.16)!important;color:#ECEAE4!important;-webkit-text-fill-color:#ECEAE4!important}
body.abjgl-lite .btn-primary{background:#F2F0EA;color:#000}
body.abjgl-lite .alert-info{background:rgba(84,169,235,.12);border-color:rgba(84,169,235,.3)}
"""

# stand-in for website_sale/static/src/js/address.js (Odoo 18): debounced
# country change -> /shop/country_info -> rebuild the province options with
# data-code; Save -> reportValidity + FormData (recorded instead of posted)
ODOO_STUB = """
(function(){
var STATES=%s;
var root=document.querySelector('.o_wsale_address_fill');
var form=document.querySelector('form.checkout_autoformat');
['name','phone','street','country_id','state_id'].forEach(function(n){if(form[n]){form[n].required=true;}});
var timer=null;
function changeCountry(init){
  var cid=parseInt(form.country_id.value,10);
  if(!cid){return;}
  setTimeout(function(){
    window.__countryInfoCalls=(window.__countryInfoCalls||0)+1;
    var sel=form.state_id;
    if(!init||sel.options.length===1){
      sel.options.length=1;
      if(cid===116){
        STATES.forEach(function(s){var o=new Option(s[1],s[0]);o.setAttribute('data-code',s[2]);sel.appendChild(o);});
        sel.parentElement.style.display='';
      }else{sel.parentElement.style.display='none';}
    }
  },250);
}
function debounced(init){clearTimeout(timer);timer=setTimeout(function(){changeCountry(init);},500);}
root.addEventListener('change',function(ev){if(ev.target&&ev.target.name==='country_id'){debounced(false);}});
debounced(true);
root.addEventListener('click',function(ev){
  var b=ev.target.closest&&ev.target.closest('#save_address');
  if(!b){return;}
  if(!form.reportValidity()){return;}
  if(ev.defaultPrevented){return;}
  ev.preventDefault();
  var data={};
  new FormData(form).forEach(function(v,k){data[k]=v;});
  window.__submitted=data;
});
})();
"""


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    arch = combined_arch()
    (out / 'combined_arch.xml').write_bytes(etree.tostring(arch, encoding='utf-8', pretty_print=True))
    stub = ODOO_STUB % json.dumps([[s.id, s.name, s.code] for s in STATES], ensure_ascii=False)
    for name, (ctx, lang) in SCENARIOS.items():
        content = QWeb().render(copy.deepcopy(arch), dict(ctx))
        for body_class in ('', 'abjgl-lite'):
            page = PAGE.format(lang=lang, theme=THEME, body_class=body_class, content=content, odoo_stub=stub)
            suffix = '_dark' if body_class else ''
            (out / ('%s%s.html' % (name, suffix))).write_text(page, encoding='utf-8')
    print('fixtures in', out)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
