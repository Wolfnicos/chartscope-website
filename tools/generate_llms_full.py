#!/usr/bin/env python3
"""Generate llms-full.txt from all ChartScope blog posts.

Concatenates all blog post body text (HTML stripped, headings preserved)
into a single Markdown file for LLM crawlers. The llms-full.txt standard
allows AI models to consume your entire site content as a knowledge source.

Usage: python3 tools/generate_llms_full.py
Output: llms-full.txt in site root
"""

import importlib.util
import re
from pathlib import Path
from datetime import datetime
from html.parser import HTMLParser


ROOT = Path(__file__).parent.parent
BLOG_DIR = ROOT / 'blog'
OUTPUT_FILE = ROOT / 'llms-full.txt'
SITE_URL = 'https://chartscope.net'

spec = importlib.util.spec_from_file_location(
    'consolidate_geo_seo', ROOT / 'tools' / 'consolidate_geo_seo.py'
)
consolidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consolidate)
NOINDEX_SLUGS = consolidate.NOINDEX_SLUGS


class MarkdownExtractor(HTMLParser):
    """Extract text from HTML, preserving headings and links."""

    def __init__(self):
        super().__init__()
        self.result = []
        self.skip = False
        self.skip_tags = {'script', 'style', 'nav', 'footer'}
        self.heading_tags = {'h1', 'h2', 'h3', 'h4'}
        self.current_tag = []
        self.link_href = None
        self.list_depth = 0

    def handle_starttag(self, tag, attrs):
        self.current_tag.append(tag)
        if tag in self.skip_tags:
            self.skip = True
        elif tag in self.heading_tags:
            level = int(tag[1])
            self.result.append('\n' + '#' * level + ' ')
        elif tag == 'a':
            for k, v in attrs:
                if k == 'href':
                    self.link_href = v
        elif tag == 'li':
            self.result.append('- ')
            self.list_depth += 1
        elif tag == 'p':
            pass
        elif tag == 'br':
            self.result.append('\n')

    def handle_endtag(self, tag):
        if tag in self.current_tag:
            self.current_tag.remove(tag)
        if tag in self.skip_tags:
            self.skip = False
        elif tag in self.heading_tags:
            self.result.append('\n\n')
        elif tag == 'a':
            if self.link_href:
                self.result.append(f' ({self.link_href})')
            self.link_href = None
        elif tag == 'p':
            self.result.append('\n\n')
        elif tag == 'li':
            self.list_depth -= 1
            self.result.append('\n')

    def handle_data(self, data):
        if not self.skip:
            text = data.strip()
            if text:
                self.result.append(text)
                if self.current_tag and self.current_tag[-1] not in self.heading_tags:
                    self.result.append(' ')


def extract_article_body(html: str) -> str:
    """Extract text from <main> or <article> or <body>."""
    # Try to get only the article content
    for tag in ('<article>', '<main class="content">', '<main>'):
        idx = html.find(tag)
        if idx != -1:
            html = html[idx:]
            break

    # Remove scripts and styles
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)

    # Convert common elements
    html = re.sub(r'<br\s*/?>', '\n', html)

    parser = MarkdownExtractor()
    parser.feed(html)
    text = ''.join(parser.result)

    # Clean up excessive newlines
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()


def generate():
    posts = sorted(
        p for p in BLOG_DIR.glob('*.html')
        if p.name not in NOINDEX_SLUGS
        and p.name != 'index.html'
        and not p.name.endswith('.html.html')
    )
    entries = []

    for post in posts:
        html = post.read_text(encoding='utf-8')

        # Extract metadata
        title_m = re.search(r'<title>([^<]+)</title>', html)
        desc_m = re.search(r'<meta name="description" content="([^"]+)"', html)
        canonical_m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
        date_m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)

        title = title_m.group(1) if title_m else post.stem
        desc = desc_m.group(1) if desc_m else ''
        url = canonical_m.group(1) if canonical_m else f'{SITE_URL}/blog/{post.name}'
        date = date_m.group(1)[:10] if date_m else ''

        body = extract_article_body(html)

        entries.append(f'## {title}\n\n'
                      f'> {desc}\n\n'
                      f'**URL:** {url}  \n'
                      f'**Published:** {date}\n\n'
                      f'{body}\n\n'
                      f'---\n')

    header = f'# ChartScope — Complete Content Index\n\n'
    header += (
        '> ChartScope is an AI-powered crypto education app for beginners. On-device ML, '
        '9 languages, privacy-first design. Indexable educational articles for LLM '
        'consumption — not financial advice.\n\n'
    )
    header += f'**Generated:** {datetime.now().strftime("%Y-%m-%d")}  \n'
    header += f'**Articles:** {len(entries)}  \n'
    header += f'**Website:** {SITE_URL}\n\n---\n\n'

    full = header + '\n'.join(entries)

    OUTPUT_FILE.write_text(full, encoding='utf-8')
    word_count = len(full.split())
    print(f'llms-full.txt generated: {OUTPUT_FILE}')
    print(f'  Articles: {len(entries)}')
    print(f'  Total words: {word_count:,}')
    print(f'  File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB')


if __name__ == '__main__':
    generate()
