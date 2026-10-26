// Browser tests for the "Use my current location" button, run against the
// replica pages from build_fixtures.py. Geolocation is emulated and every
// request is intercepted (Nominatim answers are canned), so nothing leaves
// the machine.
//
//   node test_detect_location.js FIXTURES_DIR SCREENSHOTS_DIR
const { chromium } = require('playwright');
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const FIX = process.argv[2];
const SHOTS = process.argv[3];
const STATES = require('./states_kh.json');  // [id, name, code, iso]
const URL_EN = 'https://abjskincare.com/shop/address';
const URL_KM = 'https://abjskincare.com/km/shop/address';
const PNH_NAME = STATES.find((s) => s[2] === 'PNH')[1];
const KDL_NAME = STATES.find((s) => s[2] === 'KDL')[1];

const PNH = {
  place_id: 1, licence: 'Data © OpenStreetMap contributors, ODbL 1.0. http://osm.org/copyright',
  osm_type: 'way', osm_id: 2, lat: '11.548', lon: '104.925', category: 'highway', type: 'residential',
  place_rank: 26, addresstype: 'road', name: 'ផ្លូវ ២៧១',
  display_name: 'ផ្លូវ ២៧១, ភូមិ ៣, សង្កាត់ទួលទំពូងទី ១, ខណ្ឌចំការមន, ភ្នំពេញ, 120408, កម្ពុជា',
  address: {
    road: 'ផ្លូវ ២៧១', neighbourhood: 'ភូមិ ៣', suburb: 'សង្កាត់ទួលទំពូងទី ១', city_district: 'ខណ្ឌចំការមន',
    city: 'ភ្នំពេញ', 'ISO3166-2-lvl4': 'KH-12', postcode: '120408', country: 'កម្ពុជា', country_code: 'kh',
  },
};
const PNH_TEXT = 'ផ្លូវ ២៧១, ភូមិ ៣, សង្កាត់ទួលទំពូងទី ១, ខណ្ឌចំការមន';

// no ISO code, province spelled with subscript ដ (the database uses ត), a house number
const KDL = {
  address: {
    house_number: '12', road: 'ផ្លូវជាតិលេខ ២', village: 'ភូមិព្រែកហូរ', county: 'ក្រុងតាខ្មៅ',
    state: 'ខេត្តកណ' + String.fromCharCode(0x17d2, 0x178a) + 'ាល', country: 'កម្ពុជា', country_code: 'kh',
  },
};
const KDL_TEXT = '#12 ផ្លូវជាតិលេខ ២, ភូមិព្រែកហូរ, ក្រុងតាខ្មៅ';

// English names (accept-language fallback), no ISO code
const SRP = {
  address: {
    road: 'Sivatha Boulevard', suburb: 'Svay Dankum', town: 'Siem Reap', state: 'Siem Reap Province',
    country: 'Cambodia', country_code: 'kh',
  },
};

const THAI = { address: { road: 'Sukhumvit Road', city: 'Bangkok', 'ISO3166-2-lvl4': 'TH-10', country: 'Thailand', country_code: 'th' } };

function json(body, status = 200, delayMs = 0) {
  return async (route) => {
    if (delayMs) { await new Promise((r) => setTimeout(r, delayMs)); }
    await route.fulfill({
      status,
      contentType: 'application/json; charset=utf-8',
      headers: { 'access-control-allow-origin': '*' },
      body: typeof body === 'string' ? body : JSON.stringify(body),
    });
  };
}

function today() {
  const d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}

async function open(browser, opts) {
  const {
    fixture, url = URL_EN, geo = null, allow = true, nominatim = null,
    viewport = { width: 390, height: 1100 },
  } = opts;
  const context = await browser.newContext({
    viewport, deviceScaleFactor: 2, geolocation: geo || undefined, permissions: allow ? ['geolocation'] : [],
  });
  const page = await context.newPage();
  const html = fs.readFileSync(path.join(FIX, fixture + '.html'), 'utf8');
  const calls = [];
  const errors = [];
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  page.on('console', (m) => {
    if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) { errors.push('console: ' + m.text()); }
  });
  await page.route('**/*', async (route) => {
    const u = route.request().url();
    if (u.startsWith('https://nominatim.openstreetmap.org/')) {
      calls.push(u);
      return nominatim ? nominatim(route, u) : route.abort();
    }
    if (u === url) { return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: html }); }
    return route.fulfill({ status: 404, contentType: 'text/plain', body: 'not found' });  // e.g. 4665's /web/login probe
  });
  await page.goto(url);
  return { context, page, calls, errors };
}

function state(page) {
  return page.evaluate(() => {
    const q = (id) => document.getElementById(id);
    const st = q('o_state_id');
    const opt = st.options[st.selectedIndex];
    const links = Array.from(q('abj_geo_msg').querySelectorAll('a')).map((a) => ({ text: a.textContent, href: a.getAttribute('href') }));
    return {
      street: q('o_street').value,
      state: st.value,
      stateCode: opt ? opt.getAttribute('data-code') : null,
      city: document.querySelector('input[name=city]').value,
      country: q('o_country_id').value,
      latName: q('abj_geo_lat').getAttribute('name'),
      lat: q('abj_geo_lat').value,
      lngName: q('abj_geo_lng').getAttribute('name'),
      lng: q('abj_geo_lng').value,
      dateName: q('abj_geo_date').getAttribute('name'),
      date: q('abj_geo_date').value,
      msg: q('abj_geo_msg').innerText,
      msgClass: q('abj_geo_msg').className,
      label: q('abj_geo_btn').innerText.trim(),
      links,
      submitted: window.__submitted || null,
    };
  });
}

async function detect(page) {
  await page.click('#abj_geo_btn');
  await page.waitForFunction(() => !document.getElementById('abj_geo_btn').disabled, null, { timeout: 45000 });
}

async function save(page) {
  await page.evaluate(() => { window.__submitted = null; });
  await page.click('#save_address');
  await page.waitForFunction(() => window.__submitted, null, { timeout: 5000 });
  return page.evaluate(() => window.__submitted);
}

async function fillContact(page) {
  await page.fill('#o_name', 'Dara Sok');
  await page.fill('#o_phone', '012345678');
}

const tests = [];
function test(name, fn) { tests.push({ name, fn }); }

test('precise fix in Phnom Penh fills location, province, city and pin; undo restores typed text', async (browser) => {
  const t = await open(browser, { fixture: 'existing', geo: { latitude: 11.548, longitude: 104.925, accuracy: 15 }, nominatim: json(PNH) });
  let s = await state(t.page);
  assert.strictEqual(s.latName, null, 'no pin is sent before detection');
  assert.strictEqual(s.msg, '', 'no message before detection');
  assert.strictEqual(s.label, 'Use my current location · ប្រើទីតាំងខ្ញុំ');
  await detect(t.page);
  s = await state(t.page);
  assert.strictEqual(s.street, PNH_TEXT);
  assert.strictEqual(s.state, '1777');
  assert.strictEqual(s.city, PNH_NAME, 'hidden city follows the province (view 4665)');
  assert.strictEqual(s.latName, 'partner_latitude');
  assert.strictEqual(s.lngName, 'partner_longitude');
  assert.strictEqual(s.dateName, 'date_localization');
  assert.strictEqual(s.lat, '11.5480000');
  assert.strictEqual(s.lng, '104.9250000');
  assert.strictEqual(s.date, today());
  assert.match(s.msgClass, /is_ok/);
  assert.strictEqual(s.msg.split('\n')[0], PNH_TEXT + ', ' + PNH_NAME, 'whole result shown once, with the province');
  assert.match(s.msg, /Location found \(±15 m\)/);
  assert.match(s.msg, /OpenStreetMap/);
  assert.deepStrictEqual(s.links[0], { text: 'View on map · មើលលើផែនទី', href: 'https://www.google.com/maps?q=11.5480000,104.9250000' });
  assert.ok(s.links.some((l) => /^Undo/.test(l.text)), 'undo offered because "21A 170" was replaced');
  assert.strictEqual(s.submitted, null, 'the button does not submit the form');
  assert.strictEqual(t.calls.length, 1);
  const q = new URL(t.calls[0]).searchParams;
  assert.strictEqual(q.get('format'), 'jsonv2');
  assert.strictEqual(q.get('zoom'), '18');
  assert.strictEqual(q.get('layer'), 'address');
  assert.strictEqual(q.get('accept-language'), 'km,en');
  assert.strictEqual(q.get('lat'), '11.548000');
  assert.strictEqual(q.get('lon'), '104.925000');

  const sent = await save(t.page);
  assert.strictEqual(sent.street, PNH_TEXT);
  assert.strictEqual(sent.state_id, '1777');
  assert.strictEqual(sent.city, PNH_NAME);
  assert.strictEqual(sent.partner_latitude, '11.5480000');
  assert.strictEqual(sent.partner_longitude, '104.9250000');
  assert.strictEqual(sent.date_localization, today());

  await t.page.click('#abj_geo_msg a[role=button]');
  s = await state(t.page);
  assert.strictEqual(s.street, '21A 170');
  assert.strictEqual(s.latName, 'partner_latitude', 'undoing the text keeps the detected pin');
  assert.match(s.msg, /previous text is back/);
  return t;
});

test('Kandal without ISO code: province matched by Khmer name (ដ/ត spelling), house number kept with the road', async (browser) => {
  const t = await open(browser, { fixture: 'new_kh', geo: { latitude: 11.4795, longitude: 104.9453, accuracy: 22 }, nominatim: json(KDL) });
  await fillContact(t.page);
  await detect(t.page);
  const s = await state(t.page);
  assert.strictEqual(s.street, KDL_TEXT);
  assert.strictEqual(s.state, '1778');
  assert.strictEqual(s.city, KDL_NAME);
  assert.ok(!s.links.some((l) => /^Undo/.test(l.text)), 'nothing to undo on an empty field');
  const sent = await save(t.page);
  assert.strictEqual(sent.partner_latitude, '11.4795000');
  assert.strictEqual(sent.state_id, '1778');
  return t;
});

test('English place names: province from "Siem Reap Province", town equal to the province left out', async (browser) => {
  const t = await open(browser, { fixture: 'new_kh', geo: { latitude: 13.3622, longitude: 103.8597, accuracy: 9 }, nominatim: json(SRP) });
  await detect(t.page);
  const s = await state(t.page);
  assert.strictEqual(s.street, 'Sivatha Boulevard, Svay Dankum');
  assert.strictEqual(s.state, '1779');
  assert.match(s.msg, /±9 m/);
  return t;
});

test('all 25 provinces resolve from the ISO code alone and from the Odoo Khmer name alone', async (browser) => {
  let response = null;
  const t = await open(browser, { fixture: 'new_kh', geo: { latitude: 12, longitude: 105, accuracy: 10 }, nominatim: (route) => json(response)(route) });
  let n = 0;
  for (const [id, name, code, iso] of STATES) {
    for (const kind of ['iso', 'name']) {
      n += 1;
      response = { address: kind === 'iso'
        ? { road: 'Road ' + n, 'ISO3166-2-lvl4': 'KH-' + iso, country_code: 'kh' }
        : { road: 'Road ' + n, state: name, country_code: 'kh' } };
      await t.context.setGeolocation({ latitude: 11 + n / 1000, longitude: 104 + n / 1000, accuracy: 10 });
      await detect(t.page);
      const s = await state(t.page);
      assert.strictEqual(s.state, String(id), `${code} by ${kind}`);
      assert.strictEqual(s.street, 'Road ' + n, `${code} by ${kind}: province name kept out of the location text`);
    }
  }
  assert.strictEqual(t.calls.length, 50);
  return t;
});

test('approximate fix (±1.5 km): only an empty province is filled, no text, no pin', async (browser) => {
  const t = await open(browser, { fixture: 'new_kh', geo: { latitude: 11.548, longitude: 104.925, accuracy: 1500 }, nominatim: json(PNH) });
  await detect(t.page);
  let s = await state(t.page);
  assert.strictEqual(s.street, '');
  assert.strictEqual(s.state, '1777');
  assert.strictEqual(s.latName, null);
  assert.match(s.msgClass, /is_warn/);
  assert.match(s.msg, /only approximate \(±1\.5 km\)/);
  await t.context.close();

  const u = await open(browser, { fixture: 'existing', geo: { latitude: 11.4795, longitude: 104.9453, accuracy: 1500 }, nominatim: json(KDL) });
  await detect(u.page);
  s = await state(u.page);
  assert.strictEqual(s.state, '1777', 'a province the customer already has is not overridden by a rough fix');
  assert.strictEqual(s.street, '21A 170');
  return u;
});

test('very rough fix (±20 km, IP based): no lookup, nothing changed', async (browser) => {
  const t = await open(browser, { fixture: 'existing', geo: { latitude: 11.56, longitude: 104.92, accuracy: 20000 }, nominatim: json(PNH) });
  await detect(t.page);
  const s = await state(t.page);
  assert.strictEqual(t.calls.length, 0);
  assert.strictEqual(s.street, '21A 170');
  assert.strictEqual(s.latName, null);
  assert.match(s.msg, /Could not get a precise location \(±20\.0 km\)/);
  return t;
});

test('permission denied: clear message, nothing changed', async (browser) => {
  const t = await open(browser, { fixture: 'existing', allow: false, nominatim: json(PNH) });
  await detect(t.page);
  const s = await state(t.page);
  assert.strictEqual(t.calls.length, 0);
  assert.match(s.msgClass, /is_err/);
  assert.match(s.msg, /Location access is blocked/);
  assert.strictEqual(s.street, '21A 170');
  return t;
});

test('outside Cambodia: warning, nothing changed', async (browser) => {
  const t = await open(browser, { fixture: 'existing', geo: { latitude: 13.73, longitude: 100.52, accuracy: 12 }, nominatim: json(THAI) });
  await detect(t.page);
  const s = await state(t.page);
  assert.match(s.msg, /outside Cambodia/);
  assert.strictEqual(s.street, '21A 170');
  assert.strictEqual(s.state, '1777');
  assert.strictEqual(s.latName, null);
  return t;
});

test('lookup fails (HTTP 500 / "Unable to geocode"): precise pin still saved, text untouched', async (browser) => {
  for (const nominatim of [json('Server Error', 500), json({ error: 'Unable to geocode' })]) {
    const t = await open(browser, { fixture: 'existing', geo: { latitude: 11.548, longitude: 104.925, accuracy: 15 }, nominatim });
    await detect(t.page);
    const s = await state(t.page);
    assert.strictEqual(s.street, '21A 170');
    assert.strictEqual(s.latName, 'partner_latitude');
    assert.match(s.msgClass, /is_warn/);
    assert.match(s.msg, /address name was not found/);
    const sent = await save(t.page);
    assert.strictEqual(sent.partner_latitude, '11.5480000');
    assert.deepStrictEqual(t.errors, []);
    await t.context.close();
  }
  return null;
});

test('existing pin is re-sent while the address is unchanged (base_geolocalize would zero it) and dropped when it changes', async (browser) => {
  const t = await open(browser, { fixture: 'existing_pin', nominatim: json(PNH) });
  let s = await state(t.page);
  assert.match(s.msg, /GPS location saved for delivery/);
  assert.deepStrictEqual(s.links[0], { text: 'View on map · មើលលើផែនទី', href: 'https://www.google.com/maps?q=11.5621,104.916' });
  let sent = await save(t.page);
  assert.strictEqual(sent.partner_latitude, '11.5621');
  assert.strictEqual(sent.partner_longitude, '104.916');
  assert.ok(!('date_localization' in sent), 'the capture date is only sent with a new pin');

  await t.page.fill('#o_phone', '012999888');  // phone-only edit: the pin must survive
  sent = await save(t.page);
  assert.strictEqual(sent.partner_latitude, '11.5621');

  await t.page.fill('#o_street', '21A 170, near Orussey market');
  s = await state(t.page);
  assert.strictEqual(s.latName, null);
  assert.match(s.msgClass, /is_warn/);
  assert.match(s.msg, /Address changed/);
  sent = await save(t.page);
  assert.ok(!('partner_latitude' in sent), 'a stale pin is not re-sent');

  await t.page.fill('#o_street', '21A 170');
  s = await state(t.page);
  assert.strictEqual(s.latName, 'partner_latitude');

  await t.page.selectOption('#o_state_id', '1778');
  s = await state(t.page);
  assert.strictEqual(s.latName, null, 'province change makes the pin stale too');
  return t;
});

test('province changed by the customer after detection: detected pin dropped', async (browser) => {
  const t = await open(browser, { fixture: 'existing', geo: { latitude: 11.548, longitude: 104.925, accuracy: 15 }, nominatim: json(PNH) });
  await detect(t.page);
  await t.page.selectOption('#o_state_id', '1778');
  const s = await state(t.page);
  assert.strictEqual(s.latName, null);
  assert.strictEqual(s.dateName, null);
  assert.match(s.msg, /will not be saved/);
  const sent = await save(t.page);
  assert.ok(!('partner_latitude' in sent));
  assert.strictEqual(sent.state_id, '1778');
  return t;
});

test('no country yet: detection picks Cambodia and re-selects the province after Odoo reloads the list', async (browser) => {
  const t = await open(browser, { fixture: 'anon_nocountry', geo: { latitude: 11.548, longitude: 104.925, accuracy: 15 }, nominatim: json(PNH) });
  await detect(t.page);  // before view 4575 sets the country (400 ms) and before the reload
  await t.page.waitForFunction(() => window.__countryInfoCalls >= 1, null, { timeout: 5000 });
  await t.page.waitForTimeout(300);
  let s = await state(t.page);
  assert.strictEqual(s.country, '116');
  assert.strictEqual(s.state, '1777');
  assert.strictEqual(s.stateCode, 'PNH');
  assert.strictEqual(s.city, PNH_NAME);
  assert.strictEqual(s.street, PNH_TEXT);
  assert.strictEqual(s.latName, 'partner_latitude');
  await t.context.close();

  const u = await open(browser, { fixture: 'anon_nocountry', geo: { latitude: 11.548, longitude: 104.925, accuracy: 15 }, nominatim: json(PNH) });
  await u.page.waitForFunction(() => window.__countryInfoCalls >= 1, null, { timeout: 5000 });  // 4575 + reload done
  await detect(u.page);
  s = await state(u.page);
  assert.strictEqual(s.state, '1777');
  assert.strictEqual(s.city, PNH_NAME);
  return u;
});

test('province options without data-code (older render): matched by name', async (browser) => {
  const t = await open(browser, { fixture: 'new_kh', geo: { latitude: 11.548, longitude: 104.925, accuracy: 15 }, nominatim: json(PNH) });
  await t.page.evaluate(() => document.querySelectorAll('#o_state_id option').forEach((o) => o.removeAttribute('data-code')));
  await detect(t.page);
  const s = await state(t.page);
  assert.strictEqual(s.state, '1777');
  return t;
});

test('double tap while busy sends one lookup', async (browser) => {
  const t = await open(browser, { fixture: 'new_kh', geo: { latitude: 11.548, longitude: 104.925, accuracy: 15 }, nominatim: json(PNH, 200, 1200) });
  await t.page.click('#abj_geo_btn');
  await t.page.click('#abj_geo_btn', { force: true });
  await t.page.waitForFunction(() => !document.getElementById('abj_geo_btn').disabled, null, { timeout: 10000 });
  assert.strictEqual(t.calls.length, 1);
  return t;
});

test('Khmer site: Khmer-only label and messages', async (browser) => {
  const t = await open(browser, { fixture: 'new_kh_km', url: URL_KM, geo: { latitude: 11.548, longitude: 104.925, accuracy: 15 }, nominatim: json(PNH) });
  let s = await state(t.page);
  assert.strictEqual(s.label, 'ប្រើទីតាំងបច្ចុប្បន្នរបស់ខ្ញុំ');
  await detect(t.page);
  s = await state(t.page);
  assert.match(s.msg, /រកឃើញទីតាំងហើយ \(±15 ម៉ែត្រ\)/);
  assert.ok(!/Location found/.test(s.msg));
  assert.strictEqual(s.links[0].text, 'មើលលើផែនទី');
  return t;
});

test('dark theme: status colours survive its inherited -webkit-text-fill-color', async (browser) => {
  const t = await open(browser, { fixture: 'existing_dark', geo: { latitude: 11.548, longitude: 104.925, accuracy: 15 }, nominatim: json(PNH) });
  await detect(t.page);
  const paint = await t.page.evaluate(() => {
    const css = (el) => getComputedStyle(el).webkitTextFillColor;
    return {
      status: css(document.querySelector('#abj_geo_msg .abj_geo_line:not(.abj_geo_place)')),
      place: css(document.querySelector('#abj_geo_msg .abj_geo_place')),
      label: css(document.querySelector('#abj_geo_btn .abj_geo_kh')),
    };
  });
  assert.strictEqual(paint.status, 'rgb(74, 222, 128)', 'success text is green, not the theme white');
  assert.strictEqual(paint.place, 'rgb(236, 234, 228)');
  assert.strictEqual(paint.label, 'rgb(236, 234, 228)', 'label stays light on the dark button');
  return t;
});

test('screenshots (mobile + desktop, light + dark)', async (browser) => {
  fs.mkdirSync(SHOTS, { recursive: true });
  const shoot = async (name, fixture, viewport, before) => {
    const t = await open(browser, { fixture, viewport, geo: { latitude: 11.548, longitude: 104.925, accuracy: 15 }, nominatim: json(PNH) });
    if (before) { await before(t.page); }
    const form = await t.page.$('form.checkout_autoformat');
    await form.screenshot({ path: path.join(SHOTS, name + '.png') });
    assert.deepStrictEqual(t.errors, []);
    await t.context.close();
  };
  const mobile = { width: 390, height: 1100 };
  const desktop = { width: 1280, height: 1000 };
  await shoot('1_mobile_before', 'existing', mobile);
  await shoot('2_mobile_detected', 'existing', mobile, detect);
  await shoot('3_mobile_detected_dark', 'existing_dark', mobile, detect);
  await shoot('4_mobile_existing_pin', 'existing_pin', mobile);
  await shoot('5_desktop_detected', 'existing', desktop, detect);
  await shoot('6_mobile_denied_dark', 'existing_dark', mobile, async (page) => {
    await page.context().clearPermissions();
    await detect(page);
  });
  return null;
});

(async () => {
  const browser = await chromium.launch();
  let failed = 0;
  for (const { name, fn } of tests) {
    const started = Date.now();
    try {
      const t = await fn(browser);
      if (t) {
        assert.deepStrictEqual(t.errors, [], 'no JS errors');
        await t.context.close();
      }
      console.log(`ok   ${name} (${Date.now() - started} ms)`);
    } catch (e) {
      failed += 1;
      console.log(`FAIL ${name}\n     ${(e && e.stack || e).toString().split('\n').slice(0, 6).join('\n     ')}`);
    }
  }
  await browser.close();
  console.log(failed ? `\n${failed} of ${tests.length} tests failed` : `\nall ${tests.length} tests passed`);
  process.exit(failed ? 1 : 0);
})();
