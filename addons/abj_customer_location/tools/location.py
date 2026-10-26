# -*- coding: utf-8 -*-
"""Read a map location from what customers send.

Understands Google Maps links (short ``maps.app.goo.gl`` share links and long links),
Apple Maps / OpenStreetMap / Waze links, ``geo:`` URIs and typed coordinates
(``11.5564, 104.9282``, ``11°33'23.0"N 104°55'41.6"E``, ``11.5564° N, 104.9282° E``).

Plain Python on purpose: the models turn ``LocationError`` codes into user messages and
the tests give ``resolve_url`` a fake ``fetch`` instead of going to the internet.
"""
import math
import re
import threading
from collections import OrderedDict, namedtuple
from html import unescape
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

import requests

# exact: True for a pinned point, False for the centre of the map screen (a link that only
# carries the "@lat,lng" view of the map, not a pin).
Location = namedtuple('Location', ['latitude', 'longitude', 'exact'])

# Typed coordinates need this many decimals: 4 decimals is about 11 m, 3 decimals is 110 m
# (another street). Google Maps and Telegram give 5 to 7 decimals.
MIN_DECIMALS = 4
MAX_PAGE_BYTES = 3 * 1024 * 1024
HTTP_TIMEOUT = 10
MAX_REDIRECTS = 6
EARTH_RADIUS_M = 6371000.0

SHORT_LINK_HOSTS = ('maps.app.goo.gl', 'goo.gl', 'g.co', 'share.google')
_GOOGLE_HOST_RE = re.compile(r'(?:^|\.)google\.(?:com|[a-z]{2,3}|com?\.[a-z]{2})$')
_HTTP_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/126.0 Safari/537.36'),
    'Accept-Language': 'en-US,en;q=0.8',
}

_NUM = r'-?\d{1,3}(?:\.\d+)?'
_DEC = r'-?\d{1,3}\.\d+'
# Google Maps place pin, inside the "data=" part: ...!8m2!3d11.5563738!4d104.9282099...
_PIN_RE = re.compile(r'!3d(%s)!4d(%s)' % (_NUM, _NUM))
# Directions waypoint inside "data=": !1d<longitude>!2d<latitude>
_WAYPOINT_RE = re.compile(r'!1d(%s)!2d(%s)' % (_NUM, _NUM))
# Centre of the map screen: /@11.5563738,104.9282099,17z
_VIEW_RE = re.compile(r'@(%s),(%s)(?=[,/?&#z]|$)' % (_DEC, _DEC))
# Address of the place page Google Maps serves for a link without coordinates
_PREVIEW_PLACE_RE = re.compile(r'/maps/preview/place/[^"\'\s<>]*?@(%s),(%s)' % (_DEC, _DEC))
_STATIC_MAP_RE = re.compile(r'staticmap\?[^"\'\s<>]*?(?:center|markers)=(%s),(%s)' % (_DEC, _DEC), re.IGNORECASE)
_OSM_FRAGMENT_RE = re.compile(r'map=\d{1,2}/(%s)/(%s)' % (_DEC, _DEC))
_PAIR_RE = re.compile(r'(?<![\d.])(%s)\s*(?:[,;]\s*|\s+)(%s)(?![\d.])' % (_DEC, _DEC))
_LONE_DEC_RE = re.compile(r'(?<![\d.])(%s)(?![\d.])' % _DEC)
_DMS_RE = re.compile(
    r'(\d{1,3})\s*[°º˚]\s*(\d{1,2}(?:\.\d+)?)\s*[\'′’]\s*'
    r'(?:(\d{1,2}(?:\.\d+)?)\s*(?:"|″|”|\'\'|′′)?\s*)?([NSEW])(?![a-z])', re.IGNORECASE)
_HEMISPHERE_RE = re.compile(
    r'(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*([°º˚])?\s*([NSEW])(?![a-z])', re.IGNORECASE)
_URL_RE = re.compile(r'(?:https?://|geo:|www\.|maps\.app\.goo\.gl/|goo\.gl/maps/)[^\s<>"]+', re.IGNORECASE)
# A Google Maps address inside a page that redirects with HTML instead of HTTP
_MAPS_URL_IN_PAGE_RE = re.compile(r'https?://(?:www\.|maps\.)?google\.[a-z.]{2,6}/maps[^"\'\s<>]*')
# Query parameters holding the point of a link, best first. "saddr" (the start of a route) is
# deliberately not listed.
_POINT_PARAMS = ('q', 'query', 'destination', 'daddr', 'll', 'center', 'cbll', 'viewpoint',
                 'coordinate', 'to', 'sll')

_cache = OrderedDict()
_cache_lock = threading.Lock()
_CACHE_SIZE = 200


class LocationError(Exception):
    """A location was recognised but cannot be used, or a link could not be read.

    ``code`` is one of: out_of_range, imprecise, not_allowed, unreachable, no_location_in_link.
    """

    def __init__(self, code, **params):
        super().__init__(code)
        self.code = code
        self.params = params


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------
def format_coordinate(value):
    """11.5563738 -> '11.5563738', 104.9 -> '104.9' (at most 7 decimals, no trailing zeros)."""
    return ('%.7f' % value).rstrip('0').rstrip('.')


def format_pair(latitude, longitude):
    return '%s, %s' % (format_coordinate(latitude), format_coordinate(longitude))


def maps_url(latitude, longitude):
    """Google Maps link showing a pin (opens the app on phones)."""
    return 'https://www.google.com/maps/search/?api=1&query=%s,%s' % (
        format_coordinate(latitude), format_coordinate(longitude))


def directions_url(latitude, longitude):
    """Google Maps link starting the route to the point (opens the app on phones)."""
    return 'https://www.google.com/maps/dir/?api=1&destination=%s,%s' % (
        format_coordinate(latitude), format_coordinate(longitude))


def distance_m(lat1, lng1, lat2, lng2):
    """Great-circle distance in metres between two WGS84 points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _clean(text):
    """Undo the escaping links get on their way (URL encoding, HTML and JSON escapes)."""
    text = unescape(text or '')
    text = text.replace('\\u003d', '=').replace('\\u0026', '&').replace('\\/', '/')
    for _round in range(3):
        decoded = unquote(text)
        if decoded == text:
            break
        text = decoded
    return text.replace('−', '-').replace('\xa0', ' ')


def _decimals(number):
    return len(number.split('.', 1)[1]) if '.' in number else 0


def make_location(latitude, longitude, exact=True):
    """Location for a coordinate pair; None for 0, 0 (no location); error when impossible."""
    latitude, longitude = float(latitude), float(longitude)
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        raise LocationError('out_of_range', value=format_pair(latitude, longitude))
    if abs(latitude) < 1e-9 and abs(longitude) < 1e-9:
        return None
    return Location(round(latitude, 7), round(longitude, 7), exact)


# ----------------------------------------------------------------------
# Typed coordinates
# ----------------------------------------------------------------------
def _decimal_pair(text):
    match = _PAIR_RE.search(text)
    if match:
        lat_text, lng_text = match.groups()
    else:
        # words around the numbers ("lat 11.5564 long 104.9282"): only precise numbers count
        numbers = _LONE_DEC_RE.findall(text)
        if len(numbers) != 2 or min(_decimals(number) for number in numbers) < MIN_DECIMALS:
            return None
        lat_text, lng_text = numbers
    if abs(float(lat_text)) > 90 >= abs(float(lng_text)):
        # typed "longitude, latitude" (104.9282, 11.5564): no latitude can be above 90
        lat_text, lng_text = lng_text, lat_text
    if min(_decimals(lat_text), _decimals(lng_text)) < MIN_DECIMALS:
        raise LocationError('imprecise', value='%s, %s' % (lat_text, lng_text))
    return make_location(lat_text, lng_text)


def _signed(value, hemisphere):
    return -value if hemisphere.upper() in ('S', 'W') else value


def _hemisphere_pair(matches):
    """Combine one north/south and one east/west value into a location."""
    latitude = next((value for value, hemisphere in matches if hemisphere.upper() in 'NS'), None)
    longitude = next((value for value, hemisphere in matches if hemisphere.upper() in 'EW'), None)
    if latitude is None or longitude is None:
        return None
    return make_location(latitude, longitude)


def _dms_pair(text):
    matches = []
    for degrees, minutes, seconds, hemisphere in _DMS_RE.findall(text):
        minutes, seconds = float(minutes), float(seconds or 0)
        if minutes >= 60 or seconds >= 60:
            return None
        matches.append((_signed(int(degrees) + minutes / 60 + seconds / 3600, hemisphere), hemisphere))
    return _hemisphere_pair(matches)


def _degree_hemisphere_pair(text):
    matches, values = [], []
    for value, degree_sign, hemisphere in _HEMISPHERE_RE.findall(text):
        if not degree_sign and '.' not in value:
            continue  # "Street 5 E" is not a coordinate
        matches.append((_signed(float(value), hemisphere), hemisphere))
        values.append(value)
    found = _hemisphere_pair(matches)
    if found and min(_decimals(value) for value in values) < MIN_DECIMALS:
        raise LocationError('imprecise', value=text.strip())
    return found


def location_from_text(text):
    """Location typed as text, or None."""
    text = _clean(text).replace('+', ' ')
    return _dms_pair(text) or _degree_hemisphere_pair(text) or _decimal_pair(text)


def _lenient(function, *args):
    """``function(*args)``, or None when it found something unusable: inside a link, a place
    name such as "Km 6.5" must not hide the real location found further on."""
    try:
        return function(*args)
    except LocationError:
        return None


# ----------------------------------------------------------------------
# Links
# ----------------------------------------------------------------------
def extract_url(text):
    """First link found in ``text`` (a message may hold words around the link), or ''."""
    match = _URL_RE.search(text or '')
    if not match:
        return ''
    url = match.group(0).rstrip('.,;:!?)]}\'')
    if not re.match(r'(?:https?://|geo:)', url, re.IGNORECASE):
        url = 'https://' + url
    return url


def _location_from_param(value):
    value = value.strip()
    if value.lower().startswith('loc:'):
        value = value[4:]
    if value.lower().startswith('ll.'):  # Waze: to=ll.11.5564,104.9282
        value = value[3:]
    return location_from_text(value)


def _directions_location(path, raw):
    """Destination of a directions link (/maps/dir/<from>/<to>/@...), or None."""
    segments = path.split('/maps/dir/', 1)[1].split('/')
    waypoints = []
    for segment in segments:
        if segment.startswith('@') or segment.startswith('data='):
            break
        if segment.strip():
            waypoints.append(segment)
    if waypoints:
        found = _lenient(location_from_text, waypoints[-1])
        if found:
            return found
    pairs = _WAYPOINT_RE.findall(raw)
    if pairs:
        longitude, latitude = pairs[-1]
        return make_location(latitude, longitude)
    return None


def location_from_url(url):
    """Location written in a map link, without opening it; None when the link has none."""
    raw = _clean(url)
    parts = urlsplit(raw)
    params = parse_qs(urlsplit(url).query)

    if parts.scheme.lower() == 'geo':
        # geo:11.55,104.92  /  geo:0,0?q=11.55,104.92(Shop name)
        query_point = params.get('q', [''])[0].split('(', 1)[0]
        found = location_from_text(query_point) if query_point else None
        return found or location_from_text(parts.path.split(';', 1)[0])

    match = _PIN_RE.search(raw)
    if match:
        return make_location(*match.groups())

    path = parts.path
    if '/maps/dir/' in path:
        # never fall back on the map centre of a route: it lies between start and destination
        return _directions_location(path, raw)

    for name in _POINT_PARAMS:
        for value in params.get(name, []):
            found = _lenient(_location_from_param, value)
            if found:
                return found
    if 'mlat' in params and 'mlon' in params:  # OpenStreetMap marker
        found = _lenient(make_location, params['mlat'][0], params['mlon'][0])
        if found:
            return found

    for segment in reversed(path.split('/')):
        if not segment or segment.startswith('@') or segment.startswith('data='):
            continue
        found = _lenient(location_from_text, segment)
        if found:
            return found

    match = _OSM_FRAGMENT_RE.search(parts.fragment)
    if match:
        return make_location(*match.groups(), exact=False)
    match = _VIEW_RE.search(raw)
    if match:
        return make_location(*match.groups(), exact=False)

    for values in params.values():  # a map link wrapped in another link (consent page, redirect)
        for value in values:
            if value.lower().startswith(('http://', 'https://')) and value != url:
                found = _lenient(location_from_url, value)
                if found:
                    return found
    return None


def location_from_page(page):
    """Location found in the page Google Maps serves for a place link, or None."""
    text = _clean(page)
    for pattern in (_PREVIEW_PLACE_RE, _PIN_RE, _STATIC_MAP_RE):
        match = pattern.search(text)
        if match:
            return make_location(*match.groups())
    return None


def can_resolve(url):
    """True for Google links the server may open to find the location (no other host is
    ever contacted, so a pasted link cannot make the server call an arbitrary address)."""
    parts = urlsplit(url)
    host = (parts.hostname or '').lower()
    if parts.scheme.lower() not in ('http', 'https'):
        return False
    return host in SHORT_LINK_HOSTS or bool(_GOOGLE_HOST_RE.search(host))


def http_fetch(url):
    """One HTTP GET without following redirects: (status, redirect target or None, page text)."""
    try:
        response = requests.get(url, headers=_HTTP_HEADERS, timeout=HTTP_TIMEOUT,
                                allow_redirects=False, stream=True)
    except requests.RequestException as error:
        raise LocationError('unreachable', url=url, reason=type(error).__name__) from error
    try:
        if response.is_redirect:
            return response.status_code, response.headers.get('Location'), ''
        content = response.raw.read(MAX_PAGE_BYTES, decode_content=True) or b''
        return response.status_code, None, content.decode(response.encoding or 'utf-8', errors='replace')
    finally:
        response.close()


def resolve_url(url, fetch=None):
    """Open a map link that has no coordinates in it (a short share link, a place link) and
    read the location from where it redirects to, or from the Google Maps page itself."""
    fetch = fetch or http_fetch
    current, visited = url, set()
    for _hop in range(MAX_REDIRECTS):
        if not can_resolve(current):
            raise LocationError('not_allowed', url=current)
        visited.add(current)
        status, target, page = fetch(current)
        if not target:
            if status >= 400:
                raise LocationError('unreachable', url=url, reason='HTTP %s' % status)
            found = location_from_page(page)
            if found:
                return found
            # some answers redirect with the page itself (meta refresh / script)
            match = _MAPS_URL_IN_PAGE_RE.search(_clean(page))
            if not match or match.group(0) in visited:
                raise LocationError('no_location_in_link', url=url)
            target = match.group(0)
        current = urljoin(current, target)
        found = location_from_url(current)
        if found:
            return found
    raise LocationError('unreachable', url=url, reason='too many redirects')


def _resolve_cached(url, fetch=None):
    with _cache_lock:
        if url in _cache:
            _cache.move_to_end(url)
            return _cache[url]
    found = resolve_url(url, fetch=fetch)
    with _cache_lock:
        _cache[url] = found
        while len(_cache) > _CACHE_SIZE:
            _cache.popitem(last=False)
    return found


def read_location(text, fetch=None, resolve=True):
    """Location in what was pasted (link or coordinates), or None when nothing was recognised.

    Opens Google links that carry no coordinates when ``resolve`` is set.
    Raises LocationError for something recognised but unusable.
    """
    text = (text or '').strip()
    if not text:
        return None
    url = extract_url(text)
    if not url:
        return location_from_text(text)
    found = location_from_url(url)
    if found:
        return found
    if resolve and can_resolve(url):
        return _resolve_cached(url, fetch=fetch)
    return location_from_text(text.replace(url, ' '))
