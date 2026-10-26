#!/usr/bin/env python3
"""Assemble the QWeb arch of the "detect my location" checkout view.

The arch is what gets stored in ir.ui.view.arch_db (view
website_sale.abj_detect_location, inheriting the website copy of
website_sale.address). The script and style are inlined like the other ABJ
checkout views, in CDATA so they stay readable; QWeb parses the arch as XML
and outputs text nodes raw, so they reach the browser unchanged.

    python3 build_arch.py        # writes view_arch.xml next to this file
"""
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent

BOX = """\
<div id="abj_geo_box" class="abj_geo_box">
<style><![CDATA[
{css}
]]></style>
<button type="button" id="abj_geo_btn" class="abj_geo_btn" aria-controls="abj_geo_msg">
<svg class="abj_geo_ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" \
stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">\
<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2.5" fill="currentColor"/>\
<path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg>
<span class="abj_geo_lbl">Use my current location · ប្រើទីតាំងខ្ញុំ</span>
</button>
<div id="abj_geo_msg" class="abj_geo_msg" role="status" aria-live="polite"></div>
<input type="hidden" id="abj_geo_lat" t-att-value="partner_sudo.partner_latitude or None"/>
<input type="hidden" id="abj_geo_lng" t-att-value="partner_sudo.partner_longitude or None"/>
<input type="hidden" id="abj_geo_date"/>
<script><![CDATA[
{js}
]]></script>
</div>"""

ARCH = """\
<data>
<xpath expr="//input[@id='o_street']" position="after">
{box}
</xpath>
<xpath expr="//select[@id='o_state_id']//option[@t-att-value='s.id']" position="attributes">
<attribute name="t-att-data-code">s.code</attribute>
</xpath>
</data>
"""


def build():
    css = (HERE / 'detect_location.css').read_text(encoding='utf-8').strip()
    js = (HERE / 'detect_location.js').read_text(encoding='utf-8').strip()
    for source in (css, js):
        if ']]>' in source or '</script' in source.lower() or '</style' in source.lower():
            raise ValueError('source would end its CDATA section or its HTML element early')
    arch = ARCH.format(box=BOX.format(css=css, js=js))
    etree.fromstring(arch.encode('utf-8'))  # must be well-formed for ir.ui.view
    return arch


if __name__ == '__main__':
    arch = build()
    out = HERE / 'view_arch.xml'
    out.write_text(arch, encoding='utf-8')
    print(f'wrote {out} ({len(arch)} chars)')
