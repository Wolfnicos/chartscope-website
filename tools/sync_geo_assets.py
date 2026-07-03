#!/usr/bin/env python3
"""Sync GEO assets (llms.txt, llms-full.txt, blog.html) to indexable content only."""

from __future__ import annotations

import html
import importlib.util
import re
import subprocess
import sys
from datetime import date
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

LI_STYLE = 'style="padding:1rem 0;border-bottom:1px solid #e5e7eb;list-style:none"'
BLOG_META_DESC = (
    "Educational articles on crypto chart analysis, RSI, MACD, and technical "
    "indicators. Written by ChartScope — the on-device AI crypto tutor for beginners."
)


def indexable_posts() -> list[Path]:
    return sorted(
        p
        for p in BLOG.glob("*.html")
        if p.name not in NOINDEX_SLUGS
        and p.name != "index.html"
        and not p.name.endswith(".html.html")
    )


def post_title(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"<title>([^<]+)</title>", text)
    if not m:
        return path.stem.replace("-", " ").title()
    title = m.group(1)
    title = re.sub(r"\s*[\|—-]\s*Chartscope.*$", "", title, flags=re.I).strip()
    title = re.sub(r"\s*[\|—-]\s*ChartScope.*$", "", title, flags=re.I).strip()
    return html.unescape(title)


def write_llms_txt(posts: list[Path]) -> None:
    lines = [
        "# ChartScope",
        "",
        "> ChartScope is an AI-powered crypto education app for beginners. On-device ML, "
        "chart explanations in 9 languages, privacy-first design. Educational content "
        "only — not financial advice.",
        "",
        "## Key pages",
        f"- [Home]({SITE}/): ChartScope homepage",
        f"- [Blog]({SITE}/blog.html): indexable educational articles",
        f"- [About]({SITE}/about.html): mission and team",
        f"- [Author]({SITE}/author.html): Nicolas Wolf, crypto educator",
        f"- [Support]({SITE}/support.html): help and contact",
        f"- [Privacy]({SITE}/privacy.html): privacy policy",
        "",
        "## Articles",
    ]
    for post in posts:
        slug = post.name
        title = post_title(post)
        url = f"{SITE}/blog/{slug}"
        md = BLOG / f"{post.stem}.md"
        entry = f"- [{title}]({url})"
        if md.exists():
            entry += f" — [markdown]({SITE}/blog/{md.name})"
        lines.append(entry)

    lines.extend(
        [
            "",
            "## Contact",
            f"- Website: {SITE}",
            f"- Generated: {date.today().isoformat()}",
            "",
        ]
    )
    (ROOT / "llms.txt").write_text("\n".join(lines), encoding="utf-8")


def write_blog_list(posts: list[Path]) -> None:
    blog_html = (ROOT / "blog.html").read_text(encoding="utf-8")
    blog_html = re.sub(
        r'<meta name="description" content="[^"]*">',
        f'<meta name="description" content="{BLOG_META_DESC}">',
        blog_html,
        count=1,
    )
    blog_html = re.sub(
        r'<meta property="og:description" content="[^"]*">',
        f'<meta property="og:description" content="{BLOG_META_DESC}">',
        blog_html,
        count=1,
    )

    items = []
    for post in posts:
        slug = post.name
        title = html.escape(post_title(post), quote=False)
        items.append(
            f'            <li {LI_STYLE}><a href="/blog/{slug}">'
            f"<strong>{title}</strong></a></li>"
        )
    new_ul = (
        '        <ul style="list-style:none;padding:0">\n'
        + "\n".join(items)
        + "\n        </ul>"
    )
    blog_html = re.sub(
        r"<ul style=\"list-style:none;padding:0\">.*?</ul>",
        new_ul,
        blog_html,
        count=1,
        flags=re.DOTALL,
    )
    (ROOT / "blog.html").write_text(blog_html, encoding="utf-8")


def main() -> None:
    posts = indexable_posts()
    write_llms_txt(posts)
    write_blog_list(posts)

    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "generate_llms_full.py")],
        check=True,
        cwd=ROOT,
    )

    print(f"indexable articles: {len(posts)}")
    print("updated: llms.txt, llms-full.txt, blog.html")


if __name__ == "__main__":
    main()