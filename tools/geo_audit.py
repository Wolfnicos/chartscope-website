#!/usr/bin/env python3
"""GEO Audit Tool for ChartScope blog posts.

Audits every blog post for GEO (Generative Engine Optimization) readiness:
- Schema types present (Article, FAQPage, HowTo, ItemList, etc.)
- hreflang presence
- Freshness (dateModified within 60 days)
- FAQ section presence
- Comparison table presence
- Author byline presence
- Missing schema opportunities

Usage: python3 tools/geo_audit.py
Output: geo-audit.csv (opens in any spreadsheet app)
"""

import re
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

BLOG_DIR = Path(__file__).parent.parent / 'blog'
OUTPUT_FILE = Path(__file__).parent.parent / 'geo-audit.csv'
CUTOFF_DAYS = 60

SCHEMA_TYPES = [
    'Article', 'TechArticle', 'BlogPosting',
    'FAQPage', 'Question', 'Answer',
    'HowTo', 'HowToStep',
    'ItemList', 'ListItem',
    'BreadcrumbList',
    'VideoObject',
    'Person', 'Organization',
    'DefinedTerm',
    'Review', 'SoftwareApplication',
]


def extract_schema_types(html: str) -> set[str]:
    """Extract all @type values from JSON-LD blocks."""
    types = set()
    for match in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL):
        try:
            data = json.loads(match)
            if isinstance(data, dict):
                t = data.get('@type', [])
                if isinstance(t, str):
                    types.add(t)
                elif isinstance(t, list):
                    types.update(t)
                # Check mainEntity
                me = data.get('mainEntity', {})
                if isinstance(me, dict) and me.get('@type'):
                    t2 = me['@type']
                    types.add(t2) if isinstance(t2, str) else types.update(t2)
                # Check about items
                about = data.get('about', [])
                if isinstance(about, list):
                    for a in about:
                        if isinstance(a, dict) and a.get('@type'):
                            types.add(a['@type'])
                # Check itemListElement
                items = data.get('itemListElement', [])
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict) and item.get('@type'):
                            types.add(item['@type'])
        except json.JSONDecodeError:
            pass
    return types


def has_hreflang(html: str) -> bool:
    return bool(re.search(r'<link rel="alternate" hreflang=', html))


def has_faq_section(html: str) -> bool:
    return bool(re.search(r'<h2[^>]*id="faq"|<section[^>]*class="[^"]*faq', html))


def has_comparison_table(html: str) -> bool:
    return bool(re.search(r'<table[^>]*>.*<thead>', html, re.DOTALL))


def has_author_byline(html: str) -> bool:
    return bool(re.search(r'author-byline|By Nicolas Wolf', html))


def extract_date(html: str, field: str) -> datetime | None:
    m = re.search(rf'"{field}"\s*:\s*"([^"]+)"', html)
    if m:
        try:
            return datetime.fromisoformat(m.group(1))
        except ValueError:
            pass
    return None


def freshness_status(date_str: str | None) -> str:
    if not date_str:
        return 'MISSING'
    try:
        dt = datetime.fromisoformat(date_str)
        days = (datetime.now(timezone.utc) - dt).days
        return 'FRESH' if days <= CUTOFF_DAYS else f'STALE ({days}d)'
    except (ValueError, TypeError):
        return 'INVALID'


def count_schema_types(types: set[str]) -> int:
    """Count meaningful schema types."""
    return len(types)


def audit():
    results = []
    posts = sorted(BLOG_DIR.glob('*.html'))

    for post in posts:
        html = post.read_text(encoding='utf-8')
        types = extract_schema_types(html)
        date_mod = None
        m = re.search(r'"dateModified"\s*:\s*"([^"]+)"', html)
        if m:
            date_mod = m.group(1)

        results.append({
            'file': post.name,
            'title': re.search(r'<title>([^<]+)</title>', html).group(1) if re.search(r'<title>([^<]+)</title>', html) else 'N/A',
            'schema_types': ','.join(sorted(types)),
            'schema_count': count_schema_types(types),
            'has_Article': 'Article' in types,
            'has_FAQPage': 'FAQPage' in types,
            'has_HowTo': 'HowTo' in types,
            'has_ItemList': 'ItemList' in types,
            'has_BreadcrumbList': 'BreadcrumbList' in types,
            'has_VideoObject': 'VideoObject' in types,
            'has_TechArticle': 'TechArticle' in types,
            'has_DefinedTerm': 'DefinedTerm' in types,
            'hreflang': has_hreflang(html),
            'faq_section': has_faq_section(html),
            'comparison_table': has_comparison_table(html),
            'author_byline': has_author_byline(html),
            'dateModified': date_mod or 'MISSING',
            'freshness': freshness_status(date_mod),
            'word_count': len(html.split()),
        })

    # Write CSV
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        if results:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

    # Print summary
    total = len(results)
    with_faq = sum(1 for r in results if r['has_FAQPage'])
    with_howto = sum(1 for r in results if r['has_HowTo'])
    with_itemlist = sum(1 for r in results if r['has_ItemList'])
    with_hreflang = sum(1 for r in results if r['hreflang'])
    with_techarticle = sum(1 for r in results if r['has_TechArticle'])
    fresh = sum(1 for r in results if r['freshness'] == 'FRESH')
    avg_schema = sum(r['schema_count'] for r in results) / total if total else 0
    high_schema = sum(1 for r in results if r['schema_count'] >= 7)

    print(f'GEO Audit: {total} blog posts')
    print(f'  Average schema types: {avg_schema:.1f}')
    print(f'  Posts with 7+ schema types: {high_schema}/{total} ({high_schema*100//total if total else 0}%)')
    print(f'  FAQPage:   {with_faq}/{total} ({with_faq*100//total}%)')
    print(f'  HowTo:     {with_howto}/{total} ({with_howto*100//total}%)')
    print(f'  ItemList:  {with_itemlist}/{total} ({with_itemlist*100//total}%)')
    print(f'  TechArticle: {with_techarticle}/{total}')
    print(f'  hreflang:  {with_hreflang}/{total} ({with_hreflang*100//total}%)')
    print(f'  Fresh (<{CUTOFF_DAYS}d): {fresh}/{total} ({fresh*100//total}%)')
    print(f'\nReport: {OUTPUT_FILE}')


if __name__ == '__main__':
    audit()
