#!/usr/bin/env python3
"""Replace or remove internal links from indexable posts to noindex URLs."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOG = ROOT / "blog"
SITE = "https://chartscope.net"

spec = importlib.util.spec_from_file_location(
    "consolidate_geo_seo", ROOT / "tools" / "consolidate_geo_seo.py"
)
consolidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consolidate)
NOINDEX_SLUGS = consolidate.NOINDEX_SLUGS

PILLAR = {
    "education_app": "best-crypto-education-app-for-beginners-2026.html",
    "chart_beginners": "crypto-chart-analysis-tools-tutorials-for-beginners-2026.html",
    "rsi_macd": "master-rsi-macd-crypto-chart-indicators-explained.html",
    "chartscope_review": "chartscope-review-ai-crypto-chart-analysis-app-2026.html",
    "chartscope_alt": "chartscope-alternative-understand-crypto-charts-easily.html",
    "belgium_taxes": "understanding-crypto-taxes-in-belgium-2026.html",
    "courses": "affordable-crypto-trading-courses-for-beginners-2026.html",
    "reviews": "crypto-education-app-reviews-best-for-technical-analysis-2026.html",
}

REPLACEMENTS: dict[str, str] = {
    slug: PILLAR["education_app"]
    for slug in NOINDEX_SLUGS
    if "best-crypto-education-app" in slug or "crypto-education-app-switzerland" in slug
}
REPLACEMENTS.update(
    {
        slug: PILLAR["chart_beginners"]
        for slug in NOINDEX_SLUGS
        if any(
            k in slug
            for k in (
                "chart-analysis-for-beginners",
                "learn-crypto-chart",
                "learn-crypto-charts",
                "learn-crypto-technical",
                "crypto-chart-training",
                "crypto-chart-pattern",
                "crypto-technical-analysis-for-beginners",
                "crypto-technical-analysis-formation",
                "crypto-technical-indicators-switzerland",
                "top-crypto-technical-indicators",
                "understand-crypto-charts",
                "beginner-crypto-chart-training",
                "best-crypto-chart-analysis-app",
            )
        )
    }
)
REPLACEMENTS.update(
    {
        slug: PILLAR["rsi_macd"]
        for slug in NOINDEX_SLUGS
        if "rsi-macd" in slug or "rsi_macd" in slug or "beginner-s-guide-rsi" in slug
    }
)
REPLACEMENTS.update(
    {
        "chartscope-review-ai-crypto-chart-analysis-app-france-2026.html": PILLAR[
            "chartscope_review"
        ],
        "chartscope-app-crypto-technical-analysis-germany-2026.html": PILLAR[
            "chartscope_review"
        ],
        "chartscope-alternative-better-crypto-charting-app-tutorial.html": PILLAR[
            "chartscope_alt"
        ],
        "chartscope-your-crypto-charting-education-alternative-2026.html": PILLAR[
            "chartscope_alt"
        ],
        "ai-crypto-education-app-pricing-romania-2026.html": PILLAR["education_app"],
        "chartscope-ai-crypto-education-app-price-romania-2026.html": PILLAR[
            "education_app"
        ],
        "best-crypto-education-app-in-belgium-understand-crypto-taxes.html": PILLAR[
            "belgium_taxes"
        ],
        "best-crypto-education-app-for-beginners.html": PILLAR["education_app"],
        "understand-crypto-charts-beginner-s-guide-2026.html": PILLAR["chart_beginners"],
        "free-crypto-chart-analysis-courses-for-new-traders-2026.html": PILLAR["courses"],
        "crypto-education-app-review-best-for-technical-analysis-2026.html": PILLAR[
            "reviews"
        ],
        "best-crypto-education-apps-for-rsi-macd-in-2026.html": PILLAR["rsi_macd"],
    }
)

for slug in NOINDEX_SLUGS:
    REPLACEMENTS.setdefault(slug, PILLAR["education_app"])

LI_RE = re.compile(r"<li[^>]*>.*?</li>", re.DOTALL | re.IGNORECASE)


def link_targets_noindex(fragment: str) -> str | None:
    for slug in NOINDEX_SLUGS:
        if f"/blog/{slug}" in fragment or f"{SITE}/blog/{slug}" in fragment:
            return slug
    return None


def replace_link(fragment: str, bad_slug: str, good_slug: str) -> str:
    out = fragment.replace(f"/blog/{bad_slug}", f"/blog/{good_slug}")
    out = out.replace(f"{SITE}/blog/{bad_slug}", f"{SITE}/blog/{good_slug}")
    return out


def fix_post(path: Path) -> bool:
    if path.name in NOINDEX_SLUGS or path.name == "index.html":
        return False

    html = path.read_text(encoding="utf-8")
    original = html

    for bad_slug, good_slug in REPLACEMENTS.items():
        html = html.replace(f"/blog/{bad_slug}", f"/blog/{good_slug}")
        html = html.replace(f"{SITE}/blog/{bad_slug}", f"{SITE}/blog/{good_slug}")

    def scrub_li(match: re.Match[str]) -> str:
        li = match.group(0)
        bad = link_targets_noindex(li)
        if not bad:
            return li
        good = REPLACEMENTS[bad]
        return replace_link(li, bad, good)

    html = LI_RE.sub(scrub_li, html)

    if html != original:
        path.write_text(html, encoding="utf-8")
        return True
    return False


def main() -> None:
    changed = 0
    for path in sorted(BLOG.glob("*.html")):
        if fix_post(path):
            changed += 1
            print(f"  fixed: {path.name}")
    print(f"updated {changed} posts")


if __name__ == "__main__":
    main()