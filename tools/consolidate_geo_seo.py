#!/usr/bin/env python3
"""Mark near-duplicate geo/programmatic posts as noindex and rebuild sitemap."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOG = ROOT / "blog"
SITE = "https://chartscope.net"
TODAY = date.today().isoformat()

# Keep one strong page per topic; noindex geo/marketing variants Google won't index anyway.
NOINDEX_SLUGS: set[str] = {
    # Geo — best crypto education app by country
    "best-crypto-education-app-for-beginners-france-2026.html",
    "best-crypto-education-app-luxembourg-2026-chartscope.html",
    "best-crypto-education-app-romania-2026-chartscope.html",
    "best-crypto-education-app-switzerland-2026.html",
    "best-crypto-education-app-in-belgium-understand-crypto-taxes.html",  # keep understanding-crypto-taxes-in-belgium-2026.html
    # Geo — ChartScope reviews / apps by country
    "chartscope-review-ai-crypto-chart-analysis-app-france-2026.html",
    "chartscope-app-crypto-technical-analysis-germany-2026.html",
    "chartscope-ai-crypto-education-app-price-romania-2026.html",
    "ai-crypto-education-app-pricing-romania-2026.html",
    # Geo — beginner chart analysis by country
    "crypto-chart-analysis-for-beginners-france-2026.html",
    "crypto-chart-analysis-for-beginners-luxembourg-2026.html",
    "learn-crypto-chart-analysis-for-beginners-germany-2026.html",
    "learn-crypto-chart-analysis-for-beginners-in-romania-2026.html",
    "learn-crypto-charts-online-chartscope-france.html",
    "learn-crypto-technical-analysis-france-2026.html",
    "crypto-technical-analysis-for-beginners-in-romania-2026.html",
    "crypto-chart-pattern-analysis-for-beginners-belgium.html",
    "crypto-chart-training-luxembourg-understand-charts-easily.html",
    "crypto-technical-analysis-formation-luxembourg-2026.html",
    # Geo — Switzerland / Romania variants
    "beginner-crypto-chart-training-switzerland-2026.html",
    "best-crypto-chart-analysis-app-belgium-2026.html",
    "crypto-education-app-switzerland-learn-charts-safely-2026.html",
    "crypto-technical-indicators-switzerland-understand-charts-2026.html",
    "top-crypto-technical-indicators-for-analysis-in-romania-2026.html",
    "understand-crypto-charts-in-romania-with-chartscope-2026.html",
    # RSI/MACD cluster duplicates
    "beginner-s-guide-rsi-macd-for-crypto-charts-2026.html",
    "rsi-macd-crypto-chart-indicators-explained-simply.html",
    "rsi-macd-explained-for-crypto-trading-in-2026.html",
    "rsi-macd-explained-simply-for-crypto-charts-2026.html",
    "rsi-macd-crypto-interpretation-luxembourg-2026.html",
    "understand-rsi-macd-crypto-indicators-in-france-2026.html",
    "understand-rsi-macd-for-crypto-charts-in-switzerland-2026.html",
    "understand-rsi-macd-for-crypto-in-luxembourg-2026.html",
    "best-crypto-education-apps-for-rsi-macd-in-2026.html",
    # ChartScope alternative duplicates
    "chartscope-alternative-better-crypto-charting-app-tutorial.html",
    "chartscope-your-crypto-charting-education-alternative-2026.html",
    # Other near-duplicates
    "best-crypto-education-app-for-beginners.html",  # keep ...-for-beginners-2026.html
    "crypto-education-app-review-best-for-technical-analysis-2026.html",  # keep reviews plural
    "understand-crypto-charts-beginner-s-guide-2026.html",
    "free-crypto-chart-analysis-courses-for-new-traders-2026.html",  # keep affordable-crypto-trading-courses
}

ROBOTS_META = '    <meta name="robots" content="noindex, follow">'
ROBOTS_RE = re.compile(r'<meta[^>]+name=["\']robots["\'][^>]*>', re.I)
VIEWPORT_RE = re.compile(r'(<meta[^>]+name=["\']viewport["\'][^>]*>)', re.I)

STATIC_PATHS = [
    "/",
    "/about.html",
    "/author.html",
    "/blog.html",
    "/privacy.html",
    "/support.html",
    "/terms.html",
    "/tools/position-size-calculator.html",
]


def apply_noindex(path: Path) -> bool:
    html = path.read_text(encoding="utf-8")
    if ROBOTS_RE.search(html):
        new_html = ROBOTS_RE.sub(
            '<meta name="robots" content="noindex, follow">', html, count=1
        )
    elif VIEWPORT_RE.search(html):
        new_html = VIEWPORT_RE.sub(r"\1\n" + ROBOTS_META, html, count=1)
    else:
        new_html = html.replace("<head>", "<head>\n" + ROBOTS_META + "\n", 1)

    if new_html == html:
        return False
    path.write_text(new_html, encoding="utf-8")
    return True


def write_sitemap(indexable_blog_slugs: list[str]) -> None:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path in STATIC_PATHS:
        loc = SITE + (path if path != "/" else "/")
        lines.append(f"  <url><loc>{loc}</loc><lastmod>{TODAY}</lastmod></url>")
    for slug in sorted(indexable_blog_slugs):
        lines.append(
            f"  <url><loc>{SITE}/blog/{slug}</loc><lastmod>{TODAY}</lastmod></url>"
        )
    lines.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    changed = 0
    for path in sorted(BLOG.glob("*.html")):
        if path.name == "index.html" or path.name.endswith(".html.html"):
            continue
        if path.name in NOINDEX_SLUGS and apply_noindex(path):
            changed += 1

    indexable = [
        p.name
        for p in BLOG.glob("*.html")
        if p.name not in NOINDEX_SLUGS
        and p.name != "index.html"
        and not p.name.endswith(".html.html")
    ]
    write_sitemap(indexable)

    print(f"noindex applied/updated: {changed} files")
    print(f"noindex total slugs: {len(NOINDEX_SLUGS)}")
    print(f"sitemap urls: {len(STATIC_PATHS) + len(indexable)}")


if __name__ == "__main__":
    main()