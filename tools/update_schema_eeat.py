#!/usr/bin/env python3
"""
E-E-A-T + AI Visibility schema upgrades for chartscope.net

Fixes applied:
  1. FAQPage JSON-LD injected for posts with FAQ section (h2#faq)
  2. author + publisher + keywords + wordCount added to SignalLens Article schemas
  3. BreadcrumbList schema added to posts missing it
  4. Author byline injected under H1 on SignalLens posts
  5. Person schema + sameAs added to about.html
  6. sameAs + contactPoint updated on index.html Organization schema
"""

import json
import re
from pathlib import Path
from html import unescape

BLOG_DIR = Path("/Users/lupudragos/ChartScope/chartscope-website/blog")
SITE_ROOT = Path("/Users/lupudragos/ChartScope/chartscope-website")
BASE_URL = "https://chartscope.net"
APP_URL = "https://apps.apple.com/app/chartscope/id6757865711"

AUTHOR = {
    "@type": "Person",
    "name": "Nicolas Wolf",
    "url": "https://chartscope.net/about.html",
    "sameAs": [
        "https://www.linkedin.com/in/nicolaslupu/",
        "https://github.com/Wolfnicos"
    ]
}
PUBLISHER = {
    "@type": "Organization",
    "name": "ChartScope",
    "url": BASE_URL
}

BYLINE_SENTINEL = "article-author-byline"

BYLINE_HTML = (
    '<p class="article-author-byline" style="font-size:0.88rem;color:rgba(255,255,255,0.5);'
    'margin-top:8px;margin-bottom:0;">By <a href="../about.html" '
    'style="color:rgba(255,255,255,0.6);text-decoration:none;">Nicolas Wolf</a>'
    ' &middot; ChartScope Editorial</p>'
)


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return unescape(re.sub(r"\s+", " ", text)).strip()


def count_words(html: str) -> int:
    main = re.search(r"<main[^>]*>(.*?)</main>", html, re.DOTALL)
    if main:
        return len(strip_html(main.group(1)).split())
    return 500


def get_slug_from_path(path: Path) -> str:
    return path.stem


def extract_meta(html: str, name: str) -> str:
    m = re.search(rf'<meta[^>]+name="{name}"[^>]+content="([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(rf'<meta[^>]+content="([^"]+)"[^>]+name="{name}"', html)
    return m.group(1) if m else ""


def extract_title(html: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", html)
    return m.group(1).strip() if m else ""


def extract_canonical(html: str) -> str:
    m = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', html)
    return m.group(1) if m else ""


def extract_date_published(html: str) -> str:
    m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
    return m.group(1) if m else "2026-05-18"


def extract_date_modified(html: str) -> str:
    m = re.search(r'"dateModified"\s*:\s*"([^"]+)"', html)
    return m.group(1) if m else "2026-05-18"


def is_well_built(html: str) -> bool:
    return '"author"' in html and '"keywords"' in html and 'class="cta-box"' in html


def extract_keywords_from_title(title: str, description: str) -> list:
    """Build keyword list from title + description."""
    combined = (title + " " + description).lower()
    candidates = re.findall(r"[a-z][a-z\s\-]{4,40}[a-z]", combined)
    seen, result = set(), []
    for c in candidates:
        c = c.strip()
        if c not in seen and len(c) > 5:
            seen.add(c)
            result.append(c)
        if len(result) >= 8:
            break
    return result or ["crypto", "technical analysis", "chartscope"]


# ── FAQPage Schema ──────────────────────────────────────────────────────────

def extract_faq_pairs(html: str) -> list:
    """Extract (question, answer) pairs from h2#faq section."""
    faq_match = re.search(
        r'<h2[^>]*id=["\']faq["\'][^>]*>.*?</h2>(.*?)(?=<h2|</main>|<footer)',
        html, re.DOTALL | re.IGNORECASE
    )
    if not faq_match:
        return []

    section = faq_match.group(1)
    pairs = []
    questions = list(re.finditer(r"<h3[^>]*>(.*?)</h3>(.*?)(?=<h3|$)", section, re.DOTALL))
    for q_match in questions[:6]:  # cap at 6
        question = strip_html(q_match.group(1))
        answer_html = q_match.group(2)
        # Take first <p> only — cleaner for schema
        p_match = re.search(r"<p>(.*?)</p>", answer_html, re.DOTALL)
        if p_match:
            answer = strip_html(p_match.group(1))
        else:
            answer = strip_html(answer_html)[:500]
        if question and answer:
            pairs.append((question, answer))
    return pairs


def build_faqpage_schema(pairs: list) -> str:
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": a
                }
            }
            for q, a in pairs
        ]
    }
    return f'<script type="application/ld+json">\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n</script>'


def inject_faqpage_schema(html: str) -> str:
    if '"FAQPage"' in html:
        return html
    pairs = extract_faq_pairs(html)
    if not pairs:
        return html
    schema_tag = build_faqpage_schema(pairs)
    # Inject before </head>
    return html.replace("</head>", f"\n    {schema_tag}\n</head>", 1)


# ── Article Schema — author + publisher + keywords ──────────────────────────

def upgrade_article_schema(html: str, filepath: Path) -> str:
    """Enrich the minimal SignalLens Article schema."""
    if is_well_built(html):
        return html

    pattern = re.compile(
        r'(<script type="application/ld\+json">)\s*(\{[^<]*?"@type"\s*:\s*"Article"[^<]*?\})\s*(</script>)',
        re.DOTALL
    )
    match = pattern.search(html)
    if not match:
        return html

    try:
        obj = json.loads(match.group(2))
    except json.JSONDecodeError:
        return html

    if "author" in obj:
        return html  # already enriched

    title = obj.get("headline", extract_title(html))
    description = obj.get("description", extract_meta(html, "description"))
    keywords = extract_keywords_from_title(title, description)
    word_count = count_words(html)

    obj["author"] = AUTHOR
    obj["publisher"] = PUBLISHER
    obj["keywords"] = keywords
    obj["wordCount"] = word_count
    obj["inLanguage"] = "en"

    new_schema = (
        match.group(1) + "\n" +
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n" +
        match.group(3)
    )
    return html[:match.start()] + new_schema + html[match.end():]


# ── BreadcrumbList Schema ───────────────────────────────────────────────────

def inject_breadcrumb_schema(html: str, filepath: Path) -> str:
    if '"BreadcrumbList"' in html:
        return html

    canonical = extract_canonical(html)
    title_raw = extract_title(html)
    article_name = title_raw.split("|")[0].strip() if "|" in title_raw else title_raw

    schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": BASE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": "Blog", "item": BASE_URL + "/blog.html"},
            {"@type": "ListItem", "position": 3, "name": article_name, "item": canonical or (BASE_URL + "/blog/" + filepath.name)}
        ]
    }
    schema_tag = f'<script type="application/ld+json">\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n</script>'
    return html.replace("</head>", f"\n    {schema_tag}\n</head>", 1)


# ── Author Byline ───────────────────────────────────────────────────────────

def inject_author_byline(html: str) -> str:
    if BYLINE_SENTINEL in html:
        return html
    if is_well_built(html):
        return html

    # Insert after <h1> (first one in <main>)
    main_match = re.search(r"<main[^>]*>", html)
    if not main_match:
        return html
    rest = html[main_match.end():]
    h1_match = re.search(r"</h1>", rest)
    if not h1_match:
        return html

    insert_at = main_match.end() + h1_match.end()
    return html[:insert_at] + "\n" + BYLINE_HTML + html[insert_at:]


# ── about.html — Person schema ──────────────────────────────────────────────

PERSON_SCHEMA = {
    "@context": "https://schema.org",
    "@type": "Person",
    "name": "Nicolas Wolf",
    "jobTitle": "iOS Developer & Crypto Educator",
    "url": "https://chartscope.net/about.html",
    "sameAs": [
        "https://www.linkedin.com/in/nicolaslupu/",
        "https://github.com/Wolfnicos"
    ],
    "worksFor": {
        "@type": "Organization",
        "name": "ChartScope",
        "url": "https://chartscope.net"
    }
}


def update_about_html(path: Path) -> bool:
    html = path.read_text(encoding="utf-8")
    if '"@type": "Person"' in html:
        return False
    schema_tag = (
        f'<script type="application/ld+json">\n'
        f'{json.dumps(PERSON_SCHEMA, ensure_ascii=False, indent=2)}\n'
        f'</script>'
    )
    html = html.replace("</head>", f"\n    {schema_tag}\n</head>", 1)
    path.write_text(html, encoding="utf-8")
    return True


# ── index.html — sameAs on Organization ────────────────────────────────────

def update_index_html(path: Path) -> bool:
    html = path.read_text(encoding="utf-8")
    if '"sameAs"' in html:
        return False

    # Find Organization schema and inject sameAs + app URL
    pattern = re.compile(
        r'("@type":\s*"Organization",\s*"name":\s*"ChartScope",\s*"url":\s*"https://chartscope\.net")',
        re.DOTALL
    )
    replacement = (
        '"@type": "Organization",\n'
        '      "name": "ChartScope",\n'
        '      "url": "https://chartscope.net",\n'
        '      "sameAs": [\n'
        '        "https://www.linkedin.com/in/nicolaslupu/",\n'
        '        "https://github.com/Wolfnicos",\n'
        f'        "{APP_URL}"\n'
        '      ]'
    )
    new_html, n = pattern.subn(replacement, html, count=1)
    if n == 0:
        return False
    path.write_text(new_html, encoding="utf-8")
    return True


# ── Main ────────────────────────────────────────────────────────────────────

def process_blog_file(filepath: Path) -> dict:
    original = filepath.read_text(encoding="utf-8")
    html = original

    changes = []

    new_html = inject_faqpage_schema(html)
    if new_html != html:
        changes.append("FAQPage schema")
        html = new_html

    new_html = upgrade_article_schema(html, filepath)
    if new_html != html:
        changes.append("Article schema enriched")
        html = new_html

    new_html = inject_breadcrumb_schema(html, filepath)
    if new_html != html:
        changes.append("BreadcrumbList schema")
        html = new_html

    new_html = inject_author_byline(html)
    if new_html != html:
        changes.append("author byline")
        html = new_html

    if html != original:
        filepath.write_text(html, encoding="utf-8")

    return {"file": filepath.name, "changes": changes}


def main():
    print("Processing blog posts...")
    results = []
    for f in sorted(BLOG_DIR.glob("*.html")):
        r = process_blog_file(f)
        results.append(r)
        if r["changes"]:
            print(f"  ✓ {r['file']}: {', '.join(r['changes'])}")
        else:
            print(f"  – {r['file']}: no changes")

    print("\nUpdating about.html...")
    about = SITE_ROOT / "about.html"
    changed = update_about_html(about)
    print(f"  {'✓ Person schema added' if changed else '– already up to date'}")

    print("\nUpdating index.html...")
    index = SITE_ROOT / "index.html"
    changed = update_index_html(index)
    print(f"  {'✓ sameAs added to Organization schema' if changed else '– already up to date'}")

    total_changed = sum(1 for r in results if r["changes"])
    print(f"\nDone: {total_changed}/40 blog posts updated + about.html + index.html")


if __name__ == "__main__":
    main()
