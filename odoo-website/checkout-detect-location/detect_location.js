/* ABJ checkout: "Use my current location" on the address form (/shop/address).
 *
 * Browser GPS -> OpenStreetMap Nominatim reverse geocoding -> fills the
 * Location (street) field with road / village / commune / district, selects
 * the province (the hidden city follows it, see view 4665), and sends the GPS
 * pin as partner_latitude / partner_longitude so it is saved on the customer
 * (the Contacts and Deliveries map views use it).
 *
 * The hidden pin inputs only carry a `name` while their value is trustworthy:
 * the checkout writes every named field it is given, and base_geolocalize
 * zeroes the pin whenever an address is written without one, so an existing
 * pin is re-sent as long as the address itself is unchanged.
 *
 * Plain ES5 on purpose: it is inlined in a QWeb view, like the other ABJ
 * checkout scripts, and has to run in old in-app browsers.
 */
(function () {
  'use strict';

  var NOMINATIM_URL = 'https://nominatim.openstreetmap.org/reverse';
  var PLACE_LANG = 'km,en';     // language of the place names written into the Location field
  var PRECISE_M = 300;          // accuracy up to this: fill the Location field and save the pin
  var APPROX_M = 5000;          // up to this: only suggest the province
  var GOOD_FIX_M = 30;          // stop refining once a fix is this accurate
  var SETTLE_MS = 6000;         // keep refining this long after the first fix
  var TIMEOUT_MS = 30000;       // overall, including the time the permission prompt is open
  var LOOKUP_TIMEOUT_MS = 12000;
  var REAPPLY_MS = 15000;       // re-select our province if Odoo reloads the list meanwhile

  // res.country.state code -> [ISO 3166-2:KH number, Khmer name without the
  // ខេត្ត / រាជធានី prefix, Latin spellings (lower case, letters only)]
  var PROVINCES = {
    BMC: [1, 'បន្ទាយមានជ័យ', 'banteaymeanchey banteaymeanchay'],
    BTB: [2, 'បាត់ដំបង', 'battambang batdambang'],
    KCM: [3, 'កំពង់ចាម', 'kampongcham kompongcham'],
    KCN: [4, 'កំពង់ឆ្នាំង', 'kampongchhnang kompongchhnang'],
    KSP: [5, 'កំពង់ស្ពឺ', 'kampongspeu kompongspeu kampongspoe'],
    KTM: [6, 'កំពង់ធំ', 'kampongthom kompongthom kampongthum'],
    KPT: [7, 'កំពត', 'kampot'],
    KDL: [8, 'កណ្តាល', 'kandal'],
    KKG: [9, 'កោះកុង', 'kohkong kaohkong'],
    KRT: [10, 'ក្រចេះ', 'kratie kracheh'],
    MDK: [11, 'មណ្ឌលគិរី', 'mondulkiri mondolkiri'],
    PNH: [12, 'ភ្នំពេញ', 'phnompenh phnumpenh'],
    PVH: [13, 'ព្រះវិហារ', 'preahvihear'],
    PVG: [14, 'ព្រៃវែង', 'preyveng'],
    PST: [15, 'ពោធិ៍សាត់', 'pursat pouthisat posat'],
    RTK: [16, 'រតនគិរី', 'ratanakiri ratanakkiri rattanakiri rotanakiri rotanokiri'],
    SRP: [17, 'សៀមរាប', 'siemreap siemriep siemreab'],
    PSH: [18, 'ព្រះសីហនុ', 'preahsihanouk sihanoukville sihanouk kampongsom kompongsom'],
    STG: [19, 'ស្ទឹងត្រែង', 'stungtreng stuengtreng steungtreng stoengtreng'],
    SVR: [20, 'ស្វាយរៀង', 'svayrieng'],
    TKO: [21, 'តាកែវ', 'takeo takev'],
    OMC: [22, 'ឧត្តរមានជ័យ', 'oddarmeanchey otdarmeanchey'],
    KEP: [23, 'កែប', 'kep kaeb keb'],
    PLN: [24, 'ប៉ៃលិន', 'pailin'],
    TBK: [25, 'ត្បូងឃ្មុំ', 'tbongkhmum tboungkhmum tbaungkhmum']
  };

  // Nominatim lists the address parts from the most to the least specific, and
  // which label each level gets depends on how it is mapped, so every street /
  // village / commune / district label is kept; province and country have
  // their own fields.
  var PLACE_KEYS = [
    'house_number', 'house_name', 'road', 'residential', 'hamlet', 'croft',
    'isolated_dwelling', 'neighbourhood', 'allotments', 'city_block', 'village',
    'quarter', 'suburb', 'city_district', 'district', 'borough', 'subdivision',
    'town', 'municipality', 'city', 'county', 'state_district'
  ];

  function byId(id) { return document.getElementById(id); }
  function val(el) { return el ? String(el.value || '').trim() : ''; }
  function has(obj, key) { return Object.prototype.hasOwnProperty.call(obj, key); }

  // Invisible / look-alike characters are built from their code points so the
  // source survives any copy-paste (editors strip them, tools decode escapes).
  var chr = String.fromCharCode;
  var KM_IGNORED = new RegExp('[' + chr(0x200b, 0x200c, 0x200d, 0xfeff, 0x2013, 0x2014) + '.,()-]', 'g');
  var COENG_DA = new RegExp(chr(0x17d2, 0x178a), 'g');   // subscript ដ
  var COENG_TA = chr(0x17d2, 0x178f);                     // subscript ត
  var TOANDAKHIAT = new RegExp(chr(0x17cd), 'g');         // ៍
  var LIGATURE_OE = new RegExp(chr(0x153), 'g');
  var COMBINING_MARKS = new RegExp('[' + chr(0x300) + '-' + chr(0x36f) + ']', 'g');

  // Same Khmer name whatever the spelling variant: no spaces / zero-width
  // marks, subscript ដ written as subscript ត, no ៍, no ខេត្ត / រាជធានី / ក្រុង.
  function normKm(s) {
    return String(s || '')
      .replace(/\s+/g, '')
      .replace(KM_IGNORED, '')
      .replace(COENG_DA, COENG_TA)
      .replace(TOANDAKHIAT, '')
      .replace(/^(ខេត្ត|រាជធានី|ក្រុង)/, '')
      .toLowerCase();
  }

  function normLatin(s) {
    s = String(s || '').toLowerCase().replace(LIGATURE_OE, 'oe');
    if (s.normalize) { s = s.normalize('NFD').replace(COMBINING_MARKS, ''); }
    return s.replace(/\b(province|capital|city|municipality|khett?|krong|of)\b/g, '').replace(/[^a-z]/g, '');
  }

  function isProvince(code, name) {
    var p = PROVINCES[code], k = normKm(name), l = normLatin(name);
    return (k !== '' && k === normKm(p[1])) || (l !== '' && (' ' + p[2] + ' ').indexOf(' ' + l + ' ') !== -1);
  }

  function provinceByName(name) {
    if (!name) { return null; }
    for (var code in PROVINCES) {
      if (has(PROVINCES, code) && isProvince(code, name)) { return code; }
    }
    return null;
  }

  function provinceOf(address) {
    var m = /^KH-(\d{1,2})$/i.exec(address['ISO3166-2-lvl4'] || '');
    var code, i;
    if (m) {
      for (code in PROVINCES) {
        if (has(PROVINCES, code) && PROVINCES[code][0] === Number(m[1])) { return code; }
      }
    }
    var keys = ['state', 'province', 'region', 'state_district', 'city', 'municipality', 'town', 'county'];
    for (i = 0; i < keys.length; i++) {
      code = provinceByName(address[keys[i]]);
      if (code) { return code; }
    }
    return null;
  }

  function placeText(address, provinceCode) {
    var parts = [], seen = {};
    Object.keys(address).forEach(function (key) {
      if (PLACE_KEYS.indexOf(key) === -1) { return; }
      var v = String(address[key] || '').replace(/\s+/g, ' ').trim();
      var k = normKm(v);
      if (!k || seen[k] || (provinceCode && isProvince(provinceCode, v))) { return; }
      seen[k] = true;
      parts.push(key === 'house_number' ? '#' + v.replace(/^#/, '') : v);
    });
    if (parts.length > 1 && parts[0].charAt(0) === '#') {
      parts.splice(0, 2, parts[0] + ' ' + parts[1]);
    }
    return parts.join(', ');
  }

  function stateOption(select, code) {
    if (!select || !code) { return null; }
    var i, o, want = normKm(PROVINCES[code][1]);
    for (i = 0; i < select.options.length; i++) {
      if (select.options[i].getAttribute('data-code') === code) { return select.options[i]; }
    }
    for (i = 0; i < select.options.length; i++) {
      o = select.options[i];
      if (o.value && normKm(o.text) === want) { return o; }
    }
    return null;
  }

  function selectedCode(select) {
    var o = select && select.options[select.selectedIndex];
    if (!o || !o.value) { return null; }
    var code = o.getAttribute('data-code');
    return code && has(PROVINCES, code) ? code : provinceByName(o.text);
  }

  // Best fix within a few seconds: phones usually report a coarse network fix
  // first and the GPS fix a moment later.
  function locate(onProgress) {
    return new Promise(function (resolve, reject) {
      var best = null, done = false, watchId = null, settleTimer = null;
      var hardTimer = setTimeout(function () { finish({ code: 3 }); }, TIMEOUT_MS);
      function finish(err) {
        if (done) { return; }
        done = true;
        clearTimeout(hardTimer);
        clearTimeout(settleTimer);
        if (watchId !== null) { navigator.geolocation.clearWatch(watchId); }
        if (best) { resolve(best); } else { reject(err || { code: 2 }); }
      }
      watchId = navigator.geolocation.watchPosition(function (pos) {
        if (!best || pos.coords.accuracy < best.coords.accuracy) { best = pos; }
        if (best.coords.accuracy <= GOOD_FIX_M) { finish(); return; }
        if (!settleTimer) { settleTimer = setTimeout(finish, SETTLE_MS); }
        onProgress(best.coords.accuracy);
      }, function (err) {
        // denied and unavailable are final; a timeout keeps waiting for the
        // overall timer, and any error keeps a fix we already have
        if (best || err.code !== 3) { finish(err); }
      }, { enableHighAccuracy: true, maximumAge: 0, timeout: TIMEOUT_MS });
      if (done) { navigator.geolocation.clearWatch(watchId); }
    });
  }

  var lookups = {};
  function reverseGeocode(lat, lng) {
    var key = lat.toFixed(5) + ',' + lng.toFixed(5);
    if (lookups[key]) { return Promise.resolve(lookups[key]); }
    if (!window.fetch) { return Promise.reject(new Error('fetch unavailable')); }
    var url = NOMINATIM_URL + '?format=jsonv2&addressdetails=1&zoom=18&layer=address'
      + '&accept-language=' + encodeURIComponent(PLACE_LANG)
      + '&lat=' + lat.toFixed(6) + '&lon=' + lng.toFixed(6);
    var ctrl = window.AbortController ? new AbortController() : null;
    return new Promise(function (resolve, reject) {
      var timer = setTimeout(function () {
        if (ctrl) { ctrl.abort(); }
        reject(new Error('timeout'));
      }, LOOKUP_TIMEOUT_MS);
      // Nominatim's usage policy wants the site identified: send the origin
      // as Referer even if the page itself uses a stricter referrer policy.
      fetch(url, { credentials: 'omit', referrerPolicy: 'strict-origin-when-cross-origin', signal: ctrl ? ctrl.signal : undefined })
        .then(function (r) {
          if (!r.ok) { throw new Error('HTTP ' + r.status); }
          return r.json();
        })
        .then(function (data) {
          clearTimeout(timer);
          if (data && data.address) { lookups[key] = data; }
          resolve(data);
        }, function (e) {
          clearTimeout(timer);
          reject(e);
        });
    });
  }

  function fire(el, type) { el.dispatchEvent(new Event(type, { bubbles: true })); }
  function mapUrl(lat, lng) { return 'https://www.google.com/maps?q=' + lat + ',' + lng; }
  function today() {
    var d = new Date();
    return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
  }
  function metres(acc) {
    return acc < 1000 ? { en: Math.round(acc) + ' m', kh: Math.round(acc) + ' ម៉ែត្រ' }
      : { en: (acc / 1000).toFixed(1) + ' km', kh: (acc / 1000).toFixed(1) + ' គីឡូម៉ែត្រ' };
  }

  var T = {
    locating: { en: 'Finding your location…', kh: 'កំពុងស្វែងរកទីតាំងរបស់អ្នក…' },
    refining: function (acc) {
      var d = metres(acc);
      return { en: 'Improving accuracy… ±' + d.en, kh: 'កំពុងធ្វើឱ្យទីតាំងកាន់តែច្បាស់… ±' + d.kh };
    },
    lookingUp: { en: 'Finding the address…', kh: 'កំពុងរកឈ្មោះអាសយដ្ឋាន…' },
    found: function (acc) {
      var d = metres(acc);
      return {
        en: '✓ Location found (±' + d.en + '). Please check it and add your house number.',
        kh: '✓ រកឃើញទីតាំងហើយ (±' + d.kh + ')។ សូមពិនិត្យ ហើយបន្ថែមលេខផ្ទះ។'
      };
    },
    noName: function (acc) {
      var d = metres(acc);
      return {
        en: '✓ GPS location saved (±' + d.en + '), but the address name was not found. Please type your address.',
        kh: '✓ បានរក្សាទុកទីតាំង GPS (±' + d.kh + ') ប៉ុន្តែរកឈ្មោះអាសយដ្ឋានមិនឃើញ។ សូមវាយអាសយដ្ឋាន។'
      };
    },
    approximate: function (acc) {
      var d = metres(acc);
      return {
        en: 'Your location is only approximate (±' + d.en + '). Please type your exact address, or turn on GPS and try again.',
        kh: 'ទីតាំងមិនទាន់ច្បាស់ (±' + d.kh + ')។ សូមវាយអាសយដ្ឋានឱ្យច្បាស់ ឬបើក GPS ហើយព្យាយាមម្តងទៀត។'
      };
    },
    tooRough: function (acc) {
      var d = metres(acc);
      return {
        en: 'Could not get a precise location (±' + d.en + '). Turn on GPS / Location and try again, or type your address.',
        kh: 'មិនអាចរកទីតាំងច្បាស់បានទេ (±' + d.kh + ')។ សូមបើក GPS ហើយព្យាយាមម្តងទៀត ឬវាយអាសយដ្ឋាន។'
      };
    },
    outside: {
      en: 'Your location seems to be outside Cambodia. Please type your delivery address.',
      kh: 'ទីតាំងរបស់អ្នកហាក់ដូចជានៅក្រៅប្រទេសកម្ពុជា។ សូមវាយអាសយដ្ឋានដឹកជញ្ជូន។'
    },
    denied: {
      en: 'Location access is blocked. Allow location for this site in your browser settings, or type your address.',
      kh: 'ការប្រើទីតាំងត្រូវបានបិទ។ សូមអនុញ្ញាតទីតាំងក្នុងការកំណត់ browser ឬវាយអាសយដ្ឋាន។'
    },
    unavailable: {
      en: 'Could not detect your location. Turn on GPS / Location and try again, or type your address.',
      kh: 'មិនអាចរកទីតាំងបានទេ។ សូមបើក GPS ហើយព្យាយាមម្តងទៀត ឬវាយអាសយដ្ឋាន។'
    },
    timeout: {
      en: 'Finding your location took too long. Please try again, or type your address.',
      kh: 'ការស្វែងរកទីតាំងយូរពេក។ សូមព្យាយាមម្តងទៀត ឬវាយអាសយដ្ឋាន។'
    },
    unsupported: {
      en: 'This browser cannot share your location. Please type your address.',
      kh: 'Browser នេះមិនអាចផ្ញើទីតាំងបានទេ។ សូមវាយអាសយដ្ឋាន។'
    },
    pinSaved: { en: 'GPS location saved for delivery ✓', kh: 'មានទីតាំង GPS សម្រាប់ដឹកជញ្ជូនហើយ ✓' },
    pinStale: {
      en: 'Address changed: tap the button above to update your GPS location.',
      kh: 'អាសយដ្ឋានបានផ្លាស់ប្តូរ៖ ចុចប៊ូតុងខាងលើ ដើម្បីធ្វើបច្ចុប្បន្នភាពទីតាំង GPS។'
    },
    pinDropped: {
      en: 'Address changed, so the detected GPS location will not be saved. Tap the button again if you are at the delivery address.',
      kh: 'អាសយដ្ឋានបានផ្លាស់ប្តូរ ដូច្នេះទីតាំង GPS នឹងមិនត្រូវបានរក្សាទុកទេ។ ចុចប៊ូតុងម្តងទៀត បើអ្នកនៅទីតាំងដឹកជញ្ជូន។'
    },
    restored: { en: 'Your previous text is back.', kh: 'អក្សរមុនរបស់អ្នកត្រូវបានដាក់វិញ។' },
    viewMap: { en: 'View on map', kh: 'មើលលើផែនទី' },
    undo: { en: 'Undo', kh: 'ត្រឡប់វិញ' }
  };

  function init() {
    var form = document.querySelector('form.checkout_autoformat');
    var box = byId('abj_geo_box');
    var btn = byId('abj_geo_btn');
    var msg = byId('abj_geo_msg');
    var latIn = byId('abj_geo_lat');
    var lngIn = byId('abj_geo_lng');
    var dateIn = byId('abj_geo_date');
    var street = byId('o_street');
    var stateSel = byId('o_state_id');
    var countrySel = byId('o_country_id');
    if (!form || !box || !btn || !msg || !latIn || !lngIn || !dateIn || !street) { return; }
    if (box.getAttribute('data-ready')) { return; }
    box.setAttribute('data-ready', '1');

    var km = /^km/i.test(document.documentElement.lang || '') || /^\/km(\/|$)/.test(location.pathname);
    var label = btn.querySelector('.abj_geo_lbl');
    if (label) {
      label.textContent = '';
      var kh = document.createElement('span');
      kh.className = 'abj_geo_kh';  // wrap before the Khmer words, not inside them
      kh.textContent = km ? 'ប្រើទីតាំងបច្ចុប្បន្នរបស់ខ្ញុំ' : 'ប្រើទីតាំងខ្ញុំ';
      if (!km) { label.appendChild(document.createTextNode('Use my current location · ')); }
      label.appendChild(kh);
    }

    var initial = {
      lat: parseFloat(latIn.value) || 0,
      lng: parseFloat(lngIn.value) || 0,
      street: val(street),
      state: val(stateSel),
      country: val(countrySel)
    };
    var mode = (initial.lat || initial.lng) ? 'existing' : 'none';  // 'existing' | 'detected' | 'none'
    var detected = null;   // {lat, lng, date, code}
    var busy = false, selfChange = false, wantedCode = null, wantedUntil = 0;

    function show(kind, text, links, attribution, place) {
      msg.className = 'abj_geo_msg is_' + kind;
      msg.textContent = '';
      if (place) {
        // the Location input is one line: show the whole result once
        var full = document.createElement('div');
        full.className = 'abj_geo_place';
        full.textContent = place;
        msg.appendChild(full);
      }
      var line = document.createElement('div');
      line.className = 'abj_geo_line';
      line.textContent = km ? text.kh : text.en;
      msg.appendChild(line);
      if (!km) {
        var sub = document.createElement('div');
        sub.className = 'abj_geo_line abj_geo_sub';
        sub.textContent = text.kh;
        msg.appendChild(sub);
      }
      if (links && links.length) {
        var row = document.createElement('div');
        row.className = 'abj_geo_links';
        links.forEach(function (a) { row.appendChild(a); });
        msg.appendChild(row);
      }
      if (attribution) {
        var credit = document.createElement('div');
        credit.className = 'abj_geo_attr';
        credit.appendChild(document.createTextNode('Address data © '));
        var osm = document.createElement('a');
        osm.href = 'https://www.openstreetmap.org/copyright';
        osm.target = '_blank';
        osm.rel = 'noopener';
        osm.textContent = 'OpenStreetMap';
        credit.appendChild(osm);
        msg.appendChild(credit);
      }
    }

    function link(text, href, onClick) {
      var a = document.createElement('a');
      a.textContent = km ? text.kh : text.en + ' · ' + text.kh;
      if (href) {
        a.href = href;
        a.target = '_blank';
        a.rel = 'noopener';
      } else {
        a.href = '#';
        a.setAttribute('role', 'button');
        a.addEventListener('click', function (ev) { ev.preventDefault(); onClick(); });
      }
      return a;
    }

    function setNamed(on, withDate) {
      if (on) {
        latIn.name = 'partner_latitude';
        lngIn.name = 'partner_longitude';
      } else {
        latIn.removeAttribute('name');
        lngIn.removeAttribute('name');
      }
      if (on && withDate) { dateIn.name = 'date_localization'; } else { dateIn.removeAttribute('name'); }
    }

    function addressUnchanged() {
      return val(street) === initial.street && val(stateSel) === initial.state && val(countrySel) === initial.country;
    }

    function sync() {
      if (mode === 'detected') {
        latIn.value = detected.lat;
        lngIn.value = detected.lng;
        dateIn.value = detected.date;
        setNamed(true, true);
      } else if (mode === 'existing' && addressUnchanged()) {
        latIn.value = initial.lat;
        lngIn.value = initial.lng;
        setNamed(true, false);
      } else {
        setNamed(false, false);
      }
    }

    function showExisting() {
      if (addressUnchanged()) {
        show('info', T.pinSaved, [link(T.viewMap, mapUrl(initial.lat, initial.lng))]);
      } else {
        show('warn', T.pinStale);
      }
    }

    function setValue(el, value) {
      el.value = value;
      selfChange = true;
      try { fire(el, 'input'); fire(el, 'change'); } finally { selfChange = false; }
    }

    function selectValue(el, value) {
      el.value = value;
      selfChange = true;
      try { fire(el, 'change'); } finally { selfChange = false; }
    }

    function applyWanted() {
      if (!wantedCode || !stateSel || Date.now() > wantedUntil) { return; }
      var o = stateOption(stateSel, wantedCode);
      if (o && stateSel.value !== o.value) { selectValue(stateSel, o.value); }
    }

    function chooseProvince(code) {
      wantedCode = code;
      wantedUntil = Date.now() + REAPPLY_MS;
      applyWanted();
    }

    function ensureCambodia() {
      var kh = countrySel && countrySel.querySelector('option[code="KH"]');
      if (kh && countrySel.value !== kh.value) { selectValue(countrySel, kh.value); }
    }

    function dropDetected() {
      mode = initial.lat || initial.lng ? 'existing' : 'none';
      detected = null;
      sync();
      show('warn', T.pinDropped);
    }

    function useFix(c, code) {
      detected = { lat: c.latitude.toFixed(7), lng: c.longitude.toFixed(7), date: today(), code: code };
      mode = 'detected';
      sync();
      return [link(T.viewMap, mapUrl(detected.lat, detected.lng))];
    }

    function lookupFailed(c, acc, precise) {
      if (!precise) {
        show('warn', T.approximate(acc));
        return;
      }
      show('warn', T.noName(acc), useFix(c, null));
    }

    function applyResult(data, c, acc, precise) {
      var address = data && data.address;
      var country = address && String(address.country_code || '').toLowerCase();
      if (!country) {
        lookupFailed(c, acc, precise);
        return;
      }
      if (country !== 'kh') {
        show('warn', T.outside);
        return;
      }
      var code = provinceOf(address);
      if (code) { ensureCambodia(); }
      if (!precise) {
        // a network-based fix can be a district off: only fill an empty province
        if (code && !val(stateSel)) { chooseProvince(code); }
        show('warn', T.approximate(acc), null, true);
        return;
      }
      if (code) { chooseProvince(code); }
      var text = placeText(address, code);
      var previous = street.value;
      if (text) { setValue(street, text); }
      var links = useFix(c, code);
      if (text && previous.trim() && previous.trim() !== text) {
        links.push(link(T.undo, null, function () {
          setValue(street, previous);
          show('info', T.restored, [link(T.viewMap, mapUrl(detected ? detected.lat : c.latitude, detected ? detected.lng : c.longitude))]);
        }));
      }
      var province = code ? stateOption(stateSel, code) : null;
      var place = text ? [text, province ? province.text.trim() : code ? PROVINCES[code][1] : ''].filter(Boolean).join(', ') : '';
      show('ok', text ? T.found(acc) : T.noName(acc), links, true, place);
    }

    function onPosition(pos) {
      var c = pos.coords;
      var acc = Math.max(1, Math.round(c.accuracy || 0));
      if (!(c.accuracy <= APPROX_M)) {
        show('warn', T.tooRough(acc));
        return null;
      }
      var precise = c.accuracy <= PRECISE_M;
      show('info', T.lookingUp);
      return reverseGeocode(c.latitude, c.longitude).then(function (data) {
        applyResult(data, c, acc, precise);
      }, function () {
        lookupFailed(c, acc, precise);
      });
    }

    function onLocateError(err) {
      var code = err && err.code;
      show('err', code === 1 ? T.denied : code === 3 ? T.timeout : T.unavailable);
    }

    function setBusy(on) {
      busy = on;
      btn.disabled = on;
      btn.classList.toggle('is_busy', on);
      btn.setAttribute('aria-busy', on ? 'true' : 'false');
    }

    btn.addEventListener('click', function (ev) {
      ev.preventDefault();
      if (busy) { return; }
      if (!navigator.geolocation || window.isSecureContext === false) {
        show('err', T.unsupported);
        return;
      }
      setBusy(true);
      show('info', T.locating);
      locate(function (acc) { show('info', T.refining(acc)); })
        .then(onPosition, onLocateError)
        .then(null, function () { show('err', T.unavailable); })
        .then(function () { setBusy(false); });
    });

    street.addEventListener('input', function () {
      if (selfChange || mode !== 'existing') { return; }
      sync();
      showExisting();
    });

    if (stateSel) {
      stateSel.addEventListener('change', function () {
        if (selfChange) { return; }
        wantedCode = null;   // the customer picked a province: stop re-applying ours
        if (mode === 'detected') {
          if (detected.code && selectedCode(stateSel) !== detected.code) { dropDetected(); }
        } else if (mode === 'existing') {
          sync();
          showExisting();
        }
      });
      if (window.MutationObserver) {
        // Odoo rebuilds the province list when the country changes
        new MutationObserver(applyWanted).observe(stateSel, { childList: true });
      }
    }

    if (countrySel) {
      countrySel.addEventListener('change', function () {
        if (selfChange) { return; }
        wantedCode = null;
        if (mode === 'detected') {
          dropDetected();
        } else if (mode === 'existing') {
          sync();
          showExisting();
        }
      });
    }

    sync();
    if (mode === 'existing') { showExisting(); }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
