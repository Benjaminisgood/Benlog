"""Markdown rendering and HTML cleanup for public pages."""

import re

import markdown
from bleach.css_sanitizer import CSSSanitizer
from markupsafe import Markup
import bleach

MARKDOWN_EXTENSIONS = [
    'extra',
    'admonition',
    'codehilite',
    'pymdownx.highlight',
    'pymdownx.inlinehilite',
    'pymdownx.superfences',
    'pymdownx.tilde',
    'pymdownx.tasklist',
    'pymdownx.arithmatex',
]

MARKDOWN_EXTENSION_CONFIGS = {
    'codehilite': {
        'guess_lang': False,
        'linenums': False,
        'noclasses': True,
    },
    'pymdownx.highlight': {
        'guess_lang': False,
        'anchor_linenums': True,
    },
    'pymdownx.superfences': {
        'custom_fences': [
            {
                'name': 'mermaid',
                'class': 'mermaid',
                'format': '!!python/name:pymdownx.superfences.fence_code_format',
            }
        ]
    },
    'pymdownx.arithmatex': {'generic': True},
}

ALLOWED_TAGS = [
    'a', 'abbr', 'b', 'blockquote', 'br', 'code', 'div', 'em', 'h1', 'h2', 'h3',
    'h4', 'h5', 'h6', 'hr', 'i', 'img', 'li', 'ol', 'p', 'pre', 'span', 'strong',
    'sub', 'sup', 'table', 'tbody', 'td', 'th', 'thead', 'tr', 'ul', 'del', 'kbd',
    'samp', 'details', 'summary', 'figure', 'figcaption', 'mark', 'section',
]

ALLOWED_ATTRIBUTES = {
    '*': ['class', 'id'],
    'a': ['href', 'title', 'rel'],
    'img': ['src', 'alt', 'title'],
    'code': ['class', 'style'],
    'span': ['class', 'style'],
    'div': ['class', 'style'],
    'pre': ['class', 'style'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan'],
}

_CSS = CSSSanitizer(allowed_css_properties=[
    'color', 'background', 'background-color', 'font-weight', 'font-style',
    'text-decoration', 'white-space',
])


def clean_html(html):
    html = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', html or '', flags=re.I | re.S)
    cleaned = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=['http', 'https', 'mailto'],
        css_sanitizer=_CSS,
        strip=True,
    )
    return Markup(cleaned)


def render_markdown(text):
    html = markdown.markdown(
        text or '',
        extensions=MARKDOWN_EXTENSIONS,
        extension_configs=MARKDOWN_EXTENSION_CONFIGS,
    )
    return clean_html(html)


def plain_text_from_markdown(text):
    """Cheap text extraction for search. Skips a full Markdown render."""
    if not text:
        return ''
    text = re.sub(r'```.*?```', ' ', text, flags=re.S)
    text = re.sub(r'`[^`]+`', ' ', text)
    text = re.sub(r'!\[[^\]]*\]\([^)]+\)', ' ', text)
    text = re.sub(r'\[[^\]]*\]\([^)]+\)', ' ', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'[#>*_~\-]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def is_draft(metadata):
    if not isinstance(metadata, dict):
        return False
    return str(metadata.get('status') or '').strip().lower() == 'draft'


def safe_href(url):
    """Allow site-relative paths and http(s) links. Drop javascript: and similar."""
    if not url:
        return '#'
    value = str(url).strip()
    if value.startswith('/') and not value.startswith('//') and '\\' not in value:
        return value
    lowered = value.lower()
    if lowered.startswith(('https://', 'http://', 'mailto:')):
        return value
    return '#'
