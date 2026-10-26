from odoo.tests import TransactionCase, tagged

from ..tools import location as loc

# Location headers recorded from Google (see OsmAnd discussion #17365): a share link made with
# the web version redirects to a URL holding the pin, one made with the Android app does not.
WEB_TARGET = ('https://www.google.com/maps/place/Brandenburg+Gate/@52.5162746,13.3777041,17z/'
              'data=!3m1!4b1!4m6!3m5!1s0x47a851c655f20989:0x26bbfb4e84674c63!8m2!3d52.5162746!4d13.3777041'
              '!16zL20vMDE0a2Y4?entry=tts&shorturl=1')
ANDROID_TARGET = ('https://www.google.com/maps/place/Brandenburg+Gate,+Pariser+Platz,+10117+Berlin,+Germany/'
                  'data=!4m2!3m1!1s0x47a851c655f20989:0x26bbfb4e84674c63?utm_source=mstt_1&entry=gps')
ANDROID_PAGE = (
    '<html><head><meta content="https://maps.google.com/maps/api/staticmap?center=52.5163%2C13.3777'
    '&amp;zoom=15" property="og:image"><script>window.x="https://www.google.com/maps/preview/place/'
    'Brandenburg+Gate,+Pariser+Platz/@52.5162746,13.3777041,2428a,13.1y/data\\u003d!4m2!3m1'
    '!1s0x47a851c655f20989:0x26bbfb4e84674c63"</script></head></html>')


class FakeGoogle:
    """Stands for the internet: maps each URL to (status, redirect target, page)."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        for start, answer in self.answers.items():
            if url.startswith(start):
                return answer
        raise AssertionError("unexpected request to %s" % url)


@tagged('post_install', '-at_install')
class TestLocationParser(TransactionCase):

    def setUp(self):
        super().setUp()
        loc._cache.clear()

    def assertLocation(self, text, latitude, longitude, exact=True):
        found = loc.read_location(text, resolve=False)
        self.assertTrue(found, "no location found in %r" % text)
        self.assertAlmostEqual(found.latitude, latitude, places=6, msg=text)
        self.assertAlmostEqual(found.longitude, longitude, places=6, msg=text)
        self.assertEqual(found.exact, exact, text)

    def assertLocationError(self, text, code):
        with self.assertRaises(loc.LocationError) as caught:
            loc.read_location(text, resolve=False)
        self.assertEqual(caught.exception.code, code, text)

    def test_typed_coordinates(self):
        self.assertLocation('11.5563738, 104.9282099', 11.5563738, 104.9282099)
        self.assertLocation('11.5563738,104.9282099', 11.5563738, 104.9282099)
        self.assertLocation(' 11.5563738   104.9282099 ', 11.5563738, 104.9282099)
        self.assertLocation('lat 11.5563738 long 104.9282099', 11.5563738, 104.9282099)
        # typed the wrong way round: no latitude is above 90
        self.assertLocation('104.9282099, 11.5563738', 11.5563738, 104.9282099)
        self.assertLocation('-8.6500000, 115.2166667', -8.65, 115.2166667)

    def test_degrees_minutes_seconds(self):
        self.assertLocation('11°33\'22.9"N 104°55\'41.6"E', 11.5563611, 104.9282222)
        self.assertLocation('11.5564° N, 104.9282° E', 11.5564, 104.9282)
        self.assertLocation('8°39\'00.0"S 115°13\'00.0"E', -8.65, 115.2166667)

    def test_unusable_coordinates(self):
        self.assertLocationError('11.55, 104.92', 'imprecise')
        self.assertLocationError('200.1234, 300.1234', 'out_of_range')
        self.assertIsNone(loc.read_location('Street 271 E, house 12 N', resolve=False))
        self.assertIsNone(loc.read_location('hello', resolve=False))
        self.assertIsNone(loc.read_location('   ', resolve=False))
        self.assertIsNone(loc.read_location('0.0000, 0.0000', resolve=False))

    def test_google_links(self):
        # the pin (!3d!4d) wins over the centre of the map (@)
        self.assertLocation(WEB_TARGET, 52.5162746, 13.3777041)
        self.assertLocation(
            "https://www.google.com/maps/place/11%C2%B033'22.9%22N+104%C2%B055'41.6%22E/@11.5563611,104.9256296,17z"
            "/data=!3m1!4b1!4m4!3m3!8m2!3d11.5563611!4d104.9282045", 11.5563611, 104.9282045)
        self.assertLocation('https://maps.google.com/maps?q=11.5564,104.9282&ll=11.5564,104.9282&z=16',
                            11.5564, 104.9282)
        self.assertLocation('https://www.google.com/maps/search/11.556374,+104.928210?entry=tts', 11.556374, 104.92821)
        self.assertLocation('https://www.google.com/maps/search/?api=1&query=11.5564%2C104.9282', 11.5564, 104.9282)
        self.assertLocation('https://www.google.com/maps?q=loc:11.5564+104.9282', 11.5564, 104.9282)
        # only the centre of the map: accepted, flagged as not exact
        self.assertLocation('https://www.google.com/maps/@11.5563738,104.9282099,15z?entry=ttu',
                            11.5563738, 104.9282099, exact=False)
        # a place name with numbers does not hide the location
        self.assertLocation('https://www.google.com/maps/place/Km+6.5+Road+1.2/@11.5563738,104.9282099,17z',
                            11.5563738, 104.9282099, exact=False)
        # directions: the destination, never the start nor the map centre
        self.assertLocation('https://www.google.com/maps/dir/11.5000,104.9000/11.5564,104.9282/@11.53,104.91,14z',
                            11.5564, 104.9282)
        self.assertLocation('https://www.google.com/maps/dir/My+Location/ABJ/@11.53,104.91,14z/data=!4m8!4m7'
                            '!1m0!1m5!1m1!1s0x0:0x0!2m2!1d104.9282!2d11.5564', 11.5564, 104.9282)
        # wrapped in a consent page
        self.assertLocation('https://consent.google.com/ml?continue=https://www.google.com/maps/place/X/'
                            '@11.5564,104.9282,17z/data%3D!3m1!4b1!4m6!3m5!8m2!3d11.5564!4d104.9282&gl=DE',
                            11.5564, 104.9282)

    def test_other_map_links(self):
        self.assertLocation('https://maps.apple.com/?ll=11.5564,104.9282&q=Dropped%20Pin', 11.5564, 104.9282)
        self.assertLocation('https://maps.apple.com/place?coordinate=11.5564,104.9282&name=Marked%20Location',
                            11.5564, 104.9282)
        self.assertLocation('https://www.waze.com/live-map/directions?to=ll.11.5564%2C104.9282', 11.5564, 104.9282)
        self.assertLocation('https://waze.com/ul?ll=11.5564,104.9282&navigate=yes', 11.5564, 104.9282)
        self.assertLocation('https://www.openstreetmap.org/?mlat=11.5564&mlon=104.9282#map=17/11.5564/104.9282',
                            11.5564, 104.9282)
        self.assertLocation('https://www.openstreetmap.org/#map=17/11.5564/104.9282', 11.5564, 104.9282, exact=False)
        self.assertLocation('geo:11.5564,104.9282?z=17', 11.5564, 104.9282)
        self.assertLocation('geo:0,0?q=11.5564,104.9282(ABJ)', 11.5564, 104.9282)

    def test_extract_url(self):
        self.assertEqual(loc.extract_url('Shop here: https://maps.app.goo.gl/AbC123 thanks!'),
                         'https://maps.app.goo.gl/AbC123')
        self.assertEqual(loc.extract_url('(maps.app.goo.gl/AbC123).'), 'https://maps.app.goo.gl/AbC123')
        self.assertEqual(loc.extract_url('no link'), '')

    def test_short_link_from_android(self):
        """The redirect has no coordinates: they are read from the Google Maps page."""
        google = FakeGoogle({
            'https://maps.app.goo.gl/': (302, ANDROID_TARGET, ''),
            'https://www.google.com/maps/place/': (200, None, ANDROID_PAGE),
        })
        found = loc.read_location('https://maps.app.goo.gl/PJdcARfqULFnpENj7', fetch=google)
        self.assertEqual((found.latitude, found.longitude), (52.5162746, 13.3777041))
        self.assertEqual(len(google.calls), 2)
        # read again (form preview, then save): answered from the cache
        loc.read_location('https://maps.app.goo.gl/PJdcARfqULFnpENj7', fetch=google)
        self.assertEqual(len(google.calls), 2)

    def test_short_link_from_web(self):
        google = FakeGoogle({'https://maps.app.goo.gl/': (302, WEB_TARGET, '')})
        found = loc.read_location('https://maps.app.goo.gl/Web123', fetch=google)
        self.assertEqual((found.latitude, found.longitude), (52.5162746, 13.3777041))
        self.assertEqual(len(google.calls), 1, "the page itself is not needed")

    def test_short_link_redirect_in_page(self):
        google = FakeGoogle({'https://maps.app.goo.gl/': (
            200, None, '<meta http-equiv="refresh" content="0;url=%s">' % WEB_TARGET.replace('&', '&amp;'))})
        found = loc.read_location('https://maps.app.goo.gl/Meta123', fetch=google)
        self.assertEqual((found.latitude, found.longitude), (52.5162746, 13.3777041))

    def test_short_link_failures(self):
        google = FakeGoogle({'https://maps.app.goo.gl/Dead': (404, None, 'Not found')})
        with self.assertRaises(loc.LocationError) as caught:
            loc.read_location('https://maps.app.goo.gl/Dead', fetch=google)
        self.assertEqual(caught.exception.code, 'unreachable')

        google = FakeGoogle({'https://maps.app.goo.gl/Empty': (200, None, '<html>No place</html>')})
        with self.assertRaises(loc.LocationError) as caught:
            loc.read_location('https://maps.app.goo.gl/Empty', fetch=google)
        self.assertEqual(caught.exception.code, 'no_location_in_link')

    def test_only_google_is_contacted(self):
        """A pasted link must not make the server call another address (redirect included)."""
        google = FakeGoogle({'https://maps.app.goo.gl/': (302, 'http://192.168.1.10/admin', '')})
        with self.assertRaises(loc.LocationError) as caught:
            loc.read_location('https://maps.app.goo.gl/Evil', fetch=google)
        self.assertEqual(caught.exception.code, 'not_allowed')
        self.assertEqual(google.calls, ['https://maps.app.goo.gl/Evil'])
        # other links without coordinates are not opened at all
        self.assertIsNone(loc.read_location('https://example.com/where-we-are', fetch=google))
        self.assertTrue(loc.can_resolve('https://www.google.com.kh/maps/place/x'))
        self.assertTrue(loc.can_resolve('https://goo.gl/maps/x'))
        for url in ('https://evilgoogle.com/maps', 'https://google.com.evil.io/x', 'http://127.0.0.1/',
                    'file:///etc/passwd'):
            self.assertFalse(loc.can_resolve(url), url)

    def test_links_built_for_the_user(self):
        self.assertEqual(loc.maps_url(11.55640, 104.928), 'https://www.google.com/maps/search/?api=1&query=11.5564,104.928')
        self.assertEqual(loc.directions_url(11.5564, 104.9282),
                         'https://www.google.com/maps/dir/?api=1&destination=11.5564,104.9282')
        self.assertAlmostEqual(loc.distance_m(11.5564, 104.9282, 11.5564, 104.9282), 0.0)
        self.assertAlmostEqual(loc.distance_m(11.5564, 104.9282, 11.5654, 104.9282), 1000.8, delta=1)
