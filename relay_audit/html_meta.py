"""Shared social/SEO meta tags for generated HTML reports."""
from __future__ import annotations
from html import escape

SITE_URL = "https://abcabc354.github.io/zhongzhuancha-relay-audit"
OG_IMAGE = f"{SITE_URL}/assets/og.png"


def meta_tags(title: str, description: str, canonical: str | None = None,
              image: str = OG_IMAGE) -> str:
    """Return escaped description, Open Graph and Twitter Card tags."""
    safe_title = escape(title, quote=True)
    safe_desc = escape(description, quote=True)
    safe_image = escape(image, quote=True)
    tags = [
        '<meta name="description" content="' + safe_desc + '">',
        '<meta property="og:type" content="website">',
        '<meta property="og:locale" content="zh_CN">',
        '<meta property="og:site_name" content="中转查 · relay-audit">',
        '<meta property="og:title" content="' + safe_title + '">',
        '<meta property="og:description" content="' + safe_desc + '">',
        '<meta property="og:image" content="' + safe_image + '">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:title" content="' + safe_title + '">',
        '<meta name="twitter:description" content="' + safe_desc + '">',
        '<meta name="twitter:image" content="' + safe_image + '">',
    ]
    if canonical:
        tags.append('<link rel="canonical" href="' + escape(canonical, quote=True) + '">')
        tags.append('<meta property="og:url" content="' + escape(canonical, quote=True) + '">')
    return "\n".join(tags)
