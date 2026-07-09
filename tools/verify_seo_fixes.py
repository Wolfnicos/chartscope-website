#!/usr/bin/env python3
"""Verify SEO indexing fixes for chartscope.net (local files + optional live checks)."""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://chartscope.net"


def strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return unescape(re.sub(r"\s+", " ", text)).strip()


def article_title(html: str) -> str:
    title = re.search(r"<title>([^<]+)</title>", html)
    if not title:
        return ""
    value = unescape(title.group(1)).strip()
    return re.sub(r"\s*[\|—-]\s*ChartScope.*$", "", value, flags=re.I).strip()

try:
    from consolidate_geo_seo import NOINDEX_SLUGS
except ImportError:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "consolidate_geo_seo", ROOT / "tools" / "consolidate_geo_seo.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    NOINDEX_SLUGS = mod.NOINDEX_SLUGS


def check_local() -> list[str]:
    errors: list[str] = []

    blog_html = (ROOT / "blog.html").read_text(encoding="utf-8")
    if 'rel="canonical" href="https://chartscope.net/blog/"' in blog_html:
        errors.append("blog.html still canonicalizes to broken /blog/")
    if 'rel="canonical" href="https://chartscope.net/blog.html"' not in blog_html:
        errors.append("blog.html missing canonical blog.html")

    if not (ROOT / "blog/index.html").exists():
        errors.append("missing blog/index.html redirect")
    else:
        index = (ROOT / "blog/index.html").read_text(encoding="utf-8")
        if "blog.html" not in index:
            errors.append("blog/index.html does not redirect to blog.html")

    dupes = list(ROOT.glob("blog/*.html.html"))
    if dupes:
        errors.append(f"duplicate .html.html files remain: {len(dupes)}")

    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    if 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"' not in sitemap:
        errors.append("sitemap has incorrect urlset namespace")
    if "tools/position-size-calculator.html" not in sitemap:
        errors.append("sitemap missing position-size-calculator.html")

    llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
    for md_url in re.findall(r"https://chartscope\.net/([^\s\)]+\.md)", llms):
        if not (ROOT / md_url).exists():
            errors.append(f"llms.txt links missing file: {md_url}")

    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    if "Crawl-delay" in robots:
        errors.append("robots.txt still has Crawl-delay")

    for slug in NOINDEX_SLUGS:
        path = ROOT / "blog" / slug
        if not path.exists():
            errors.append(f"noindex slug missing file: {slug}")
            continue
        html = path.read_text(encoding="utf-8")
        if "noindex" not in html.lower():
            errors.append(f"missing noindex meta: blog/{slug}")
        if f"/blog/{slug}</loc>" in sitemap:
            errors.append(f"noindex page still in sitemap: {slug}")

    llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
    if "SignalLens" in llms:
        errors.append("llms.txt still mentions SignalLens")
    for slug in NOINDEX_SLUGS:
        if f"/blog/{slug}" in llms:
            errors.append(f"llms.txt links noindex page: {slug}")

    blog_html = (ROOT / "blog.html").read_text(encoding="utf-8")
    for slug in NOINDEX_SLUGS:
        if f'href="/blog/{slug}"' in blog_html:
            errors.append(f"blog.html links noindex page: {slug}")
    if len(blog_html) and 'name="description" content="Articles and updates' in blog_html:
        errors.append("blog.html still has short generic meta description")

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "update_schema_geo", ROOT / "tools" / "update_schema_geo.py"
    )
    geo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(geo)

    indexable = [
        p
        for p in (ROOT / "blog").glob("*.html")
        if p.name not in NOINDEX_SLUGS
        and p.name != "index.html"
        and not p.name.endswith(".html.html")
    ]
    for path in indexable:
        html = path.read_text(encoding="utf-8")
        h1s = re.findall(r"<h1[^>]*>.*?</h1>", html, flags=re.DOTALL | re.IGNORECASE)
        expected_h1 = article_title(html)
        if expected_h1 and h1s and strip_tags(h1s[0]) != expected_h1:
            errors.append(f"primary h1 mismatch: {path.name}")
        for h1 in h1s:
            if "<p" in h1.lower() or "article-author-byline" in h1:
                errors.append(f"invalid paragraph/byline inside h1: {path.name}")
        if geo.extract_faq_pairs(html) and '"FAQPage"' not in html:
            errors.append(f"FAQ section without FAQPage schema: {path.name}")
        if re.search(r'"dateModified"\s*:\s*"\d{4}-\d{2}-\d{2}"', html):
            errors.append(f"dateModified not ISO 8601: {path.name}")
        for slug in NOINDEX_SLUGS:
            if f"/blog/{slug}" in html or f"{SITE}/blog/{slug}" in html:
                errors.append(f"indexable post links noindex URL: {path.name} -> {slug}")

    return errors


def check_live() -> list[str]:
    errors: list[str] = []
    ctx = None
    import ssl

    ctx = ssl.create_default_context()

    def fetch(url: str) -> tuple[int, str]:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=25) as resp:
                return resp.status, resp.read(200000).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(100000).decode("utf-8", errors="replace")

    checks = {
        f"{SITE}/blog.html": 200,
        f"{SITE}/blog/": 200,
        f"{SITE}/blog/index.html": 200,
        f"{SITE}/tools/position-size-calculator.html": 200,
        f"{SITE}/blog/learn-crypto-charts-online-chartscope-france.html.html": 404,
        f"{SITE}/blog/master-rsi-macd-crypto-chart-indicators-explained.html.html": 404,
        f"{SITE}/blog/best-crypto-education-app-in-belgium-understand-crypto-taxes.html.html": 404,
    }

    for url, expected in checks.items():
        code, body = fetch(url)
        if code != expected:
            errors.append(f"live {url}: expected {expected}, got {code}")

    for url in (f"{SITE}/blog.html", f"{SITE}/blog/"):
        _, body = fetch(url)
        canon = re.search(r'rel="canonical" href="([^"]+)"', body)
        if not canon or canon.group(1) != f"{SITE}/blog.html":
            errors.append(f"live canonical mismatch on {url}: {canon.group(1) if canon else 'missing'}")

    _, sitemap_body = fetch(f"{SITE}/sitemap.xml")
    if 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"' not in sitemap_body:
        errors.append("live sitemap has incorrect urlset namespace")

    return errors


def main() -> int:
    live = "--live" in sys.argv
    local_errors = check_local()
    print("LOCAL CHECKS")
    if local_errors:
        for err in local_errors:
            print(f"  FAIL: {err}")
    else:
        print("  OK: all local checks passed")

    if live:
        print("\nLIVE CHECKS")
        live_errors = check_live()
        if live_errors:
            for err in live_errors:
                print(f"  FAIL: {err}")
        else:
            print("  OK: all live checks passed")
        return 1 if local_errors or live_errors else 0

    return 1 if local_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
