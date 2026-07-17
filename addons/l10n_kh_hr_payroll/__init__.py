import logging
import os

from . import models

_logger = logging.getLogger(__name__)

# The Khmer font is normally shipped with the module. When the module is
# deployed from a slim package that excludes binaries, fetch it at install
# time; if that is not possible the PDF reports fall back to the system
# Khmer fonts declared in static/src/css/khmer_fonts.css.
FONT_SOURCES = {
    'NotoSansKhmer-Regular.ttf':
        'https://raw.githubusercontent.com/notofonts/khmer/main/fonts/'
        'NotoSansKhmer/hinted/ttf/NotoSansKhmer-Regular.ttf',
    'OFL.txt': 'https://raw.githubusercontent.com/notofonts/khmer/main/OFL.txt',
}


def post_init_hook(env):
    fonts_dir = os.path.join(os.path.dirname(__file__), 'static', 'fonts')
    try:
        os.makedirs(fonts_dir, exist_ok=True)
    except OSError as e:
        _logger.warning("l10n_kh_hr_payroll: cannot create %s (%s)", fonts_dir, e)
        return
    for filename, url in FONT_SOURCES.items():
        path = os.path.join(fonts_dir, filename)
        if os.path.exists(path):
            continue
        try:
            import requests
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            content = resp.content
            if filename.endswith('.ttf') and content[:4] not in (
                    b'\x00\x01\x00\x00', b'true', b'OTTO'):
                raise ValueError("downloaded file is not a TrueType font")
            with open(path, 'wb') as f:
                f.write(content)
            _logger.info("l10n_kh_hr_payroll: fetched %s", filename)
        except Exception as e:
            _logger.warning(
                "l10n_kh_hr_payroll: could not fetch %s (%s); Khmer PDF "
                "rendering will rely on system fonts (e.g. fonts-khmeros)",
                filename, e)
