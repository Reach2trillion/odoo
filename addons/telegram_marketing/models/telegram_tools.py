# -*- coding: utf-8 -*-
"""Helpers shared by the Telegram models: HTML conversion, text splitting, API errors."""
import html as html_lib
import re

from lxml import etree, html as lxml_html

# Telegram counts UTF-16 code units; stay a bit below the official 4096 / 1024 limits
# so that emojis (2 code units each) never push a message over the edge.
TELEGRAM_TEXT_LIMIT = 4000
TELEGRAM_CAPTION_LIMIT = 1000
TELEGRAM_MAX_DOWNLOAD = 20 * 1024 * 1024  # Bot API: getFile works up to 20 MB
TELEGRAM_MAX_PHOTO = 10 * 1024 * 1024     # sendPhoto accepts up to 10 MB


class TelegramError(Exception):
    """Error returned by the Telegram Bot API, or a transport problem while calling it."""

    def __init__(self, description, error_code=None, retry_after=None):
        super().__init__(description)
        self.description = description
        self.error_code = error_code
        self.retry_after = retry_after

    @property
    def is_unreachable_chat(self):
        """The chat cannot be reached anymore: user blocked the bot, bot kicked, account deleted..."""
        if self.error_code == 403:
            return True
        description = (self.description or '').lower()
        return self.error_code == 400 and any(
            needle in description for needle in ('chat not found', 'user is deactivated', 'peer_id_invalid')
        )

    @property
    def is_rate_limited(self):
        return self.error_code == 429


_INLINE_TAGS = {
    'b': 'b', 'strong': 'b',
    'i': 'i', 'em': 'i',
    'u': 'u', 'ins': 'u',
    's': 's', 'strike': 's', 'del': 's',
    'code': 'code', 'pre': 'pre', 'blockquote': 'blockquote',
    'tg-spoiler': 'tg-spoiler',
}
_HEADING_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
_BLOCK_TAGS = {
    'p', 'div', 'section', 'article', 'header', 'footer', 'address', 'figure', 'figcaption',
    'table', 'thead', 'tbody', 'tfoot', 'tr', 'ul', 'ol', 'li', 'dl', 'dt', 'dd', 'pre',
    'blockquote', 'hr', 'form', 'fieldset', 'main', 'nav', 'aside',
} | _HEADING_TAGS
_SKIP_TAGS = {
    'script', 'style', 'head', 'title', 'meta', 'link', 'noscript', 'template', 'svg',
    'iframe', 'object', 'embed', 'canvas', 'video', 'audio', 'button', 'select', 'input', 'textarea',
}
_WHITESPACE_RE = re.compile(r'\s+')
_TAG_RE = re.compile(r'<[^>]*>')
_ALLOWED_HREF_RE = re.compile(r'^(https?://|tg://|mailto:|tel:)', re.I)
_PLACEHOLDER_DEFAULT_RE = re.compile(r'\|\|\|[\s\xa0]*(.*?)[\s\xa0]*\}\}')


def normalize_placeholders(text):
    """Trim the spaces around placeholder defaults: ``{{ x ||| there }}`` -> ``{{ x |||there}}``.

    Odoo keeps the trailing spaces of the default value, which would give "Hi there ,".
    """
    if not text:
        return text
    return _PLACEHOLDER_DEFAULT_RE.sub(lambda match: '|||' + match.group(1) + '}}', str(text))


def escape_text(text):
    """Escape plain text so that it can be sent with parse_mode=HTML."""
    return html_lib.escape(text or '', quote=False)


def telegram_html_to_text(text):
    """Strip the Telegram HTML tags we produce (for previews and logs)."""
    return html_lib.unescape(_TAG_RE.sub('', text or ''))


def html_to_telegram(html_content):
    """Convert Odoo (sanitized) HTML into the small HTML subset accepted by the Telegram Bot API.

    Supported: bold, italic, underline, strikethrough, spoiler, code, pre, blockquote and links.
    Paragraphs, line breaks, headings and lists are converted to text layout; everything
    else is flattened to text. Text is escaped as required by Telegram.
    """
    if not html_content:
        return ''
    html_content = str(html_content)
    try:
        root = lxml_html.fragment_fromstring(html_content, create_parent='div')
    except (etree.ParserError, etree.XMLSyntaxError, ValueError, TypeError):
        return _clean_output(escape_text(html_lib.unescape(_TAG_RE.sub('', html_content))))
    out = []
    _render_node(root, out, [], in_pre=False)
    return _clean_output(''.join(out))


def _clean_output(text):
    text = text.replace('\xa0', ' ')
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n[ \t]+', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _ensure_newline(out):
    current = ''.join(out).rstrip(' \t')
    if current and not current.endswith('\n'):
        out.append('\n')


def _append_text(out, text, in_pre):
    if not text:
        return
    if not in_pre:
        text = _WHITESPACE_RE.sub(' ', text)
    out.append(escape_text(text))


def _render_node(node, out, list_stack, in_pre):
    tag = node.tag if isinstance(node.tag, str) else None
    if tag is None or tag.lower() in _SKIP_TAGS:  # comments, processing instructions, scripts...
        _append_text(out, node.tail, in_pre)
        return
    tag = tag.lower()
    if tag == 'br':
        out.append('\n')
    elif tag == 'hr':
        _ensure_newline(out)
        out.append('———\n')
    elif tag == 'img':
        _append_text(out, node.get('alt'), in_pre)
    else:
        is_block = tag in _BLOCK_TAGS
        if tag in ('ul', 'ol'):
            list_stack.append([tag, 0])
        if is_block:
            _ensure_newline(out)
        if tag == 'li':
            if list_stack and list_stack[-1][0] == 'ol':
                list_stack[-1][1] += 1
                out.append('%d. ' % list_stack[-1][1])
            else:
                out.append('• ')

        wrapper = href = None
        if tag in _HEADING_TAGS:
            wrapper = 'b'
        elif tag in _INLINE_TAGS:
            wrapper = _INLINE_TAGS[tag]
        elif tag == 'span' and 'tg-spoiler' in (node.get('class') or ''):
            wrapper = 'tg-spoiler'
        elif tag == 'a':
            href = (node.get('href') or '').strip()
            if not _ALLOWED_HREF_RE.match(href):
                href = None

        inner = []
        child_in_pre = in_pre or tag in ('pre', 'code')
        _append_text(inner, node.text, child_in_pre)
        for child in node:
            _render_node(child, inner, list_stack, child_in_pre)
        inner_text = ''.join(inner)

        if wrapper and inner_text.strip():
            out.append('<%s>%s</%s>' % (wrapper, inner_text, wrapper))
        elif href and inner_text.strip():
            out.append('<a href="%s">%s</a>' % (html_lib.escape(href, quote=True), inner_text))
        else:
            out.append(inner_text)

        if tag in ('ul', 'ol'):
            list_stack.pop()
        if is_block:
            _ensure_newline(out)
    _append_text(out, node.tail, in_pre)


def split_text(text, limit=TELEGRAM_TEXT_LIMIT):
    """Split a long text in chunks, preferably on line breaks, then on spaces."""
    text = text or ''
    if len(text) <= limit:
        return [text]
    chunks = []
    while len(text) > limit:
        cut = text.rfind('\n', 0, limit)
        if cut < limit // 2:
            cut = text.rfind(' ', 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    if text:
        chunks.append(text)
    return chunks
