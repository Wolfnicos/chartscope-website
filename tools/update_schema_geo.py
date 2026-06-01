#!/usr/bin/env python3
"""
GEO Schema Batch Upgrade for chartscope.net

Adds to all blog posts:
  1. hreflang tags (en + x-default)
  2. Improved author byline with credentials
  3. BreadcrumbList schema (if missing)
  4. FAQPage schema (if FAQ section present + schema missing)
  5. ItemList schema (for listicle posts with numbered H2 sections)
  6. HowTo schema (for tutorial posts with step-by-step content)
  7. Article schema enriched with author/publisher/keywords/wordCount

Usage: python3 tools/update_schema_geo.py
"""

import json
import re
from pathlib import Path
from html import unescape
from datetime import datetime

BLOG_DIR = Path(__file__).parent.parent / 'blog'
BASE_URL = "https://chartscope.net"

AUTHOR = {
    "@type": "Person",
    "name": "Nicolas Wolf",
    "url": "https://chartscope.net/author.html",
    "sameAs": [
        "https://www.linkedin.com/in/nicolaslupu/",
        "https://github.com/Wolfnicos"
    ]
}
PUBLISHER = {"@type": "Organization", "name": "ChartScope", "url": BASE_URL}

BYLINE_SENTINEL = "article-author-byline"
IMPROVED_BYLINE = (
    '<p class="article-author-byline" style="font-size:0.9rem;color:rgba(255,255,255,0.55);'
    'margin-top:8px;margin-bottom:24px;">By <a href="../author.html" '
    'style="color:rgba(255,255,255,0.65);text-decoration:none;font-weight:500;">Nicolas Wolf</a>'
    ' — iOS Developer, Crypto Educator &amp; Creator of ChartScope. 5+ years analyzing crypto markets.</p>'
)

TODAY = datetime.now().strftime("%Y-%m-%d")


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return unescape(re.sub(r"\s+", " ", text)).strip()


def count_words(html: str) -> int:
    main = re.search(r"<main[^>]*>(.*?)</main>", html, re.DOTALL)
    if main:
        return len(strip_html(main.group(1)).split())
    return 500


def extract_title(html: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", html)
    return m.group(1).strip() if m else ""


def extract_canonical(html: str) -> str:
    m = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', html)
    return m.group(1) if m else ""


def extract_description(html: str) -> str:
    m = re.search(r'<meta name="description" content="([^"]+)"', html)
    return m.group(1) if m else ""


def extract_article_name(html: str) -> str:
    title = extract_title(html)
    return title.split("|")[0].strip() if "|" in title else title


def extract_keywords_from_title(title: str, description: str) -> list:
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


# ── Hreflang Injection ──────────────────────────────────────────────────────

def inject_hreflang(html: str, filepath: Path) -> str:
    if '<link rel="alternate" hreflang=' in html:
        return html

    canonical = extract_canonical(html)
    if not canonical:
        canonical = f"{BASE_URL}/blog/{filepath.name}"

    hreflang_tags = (
        f'    <link rel="alternate" hreflang="en" href="{canonical}">\n'
        f'    <link rel="alternate" hreflang="x-default" href="{canonical}">'
    )

    # Inject after canonical link
    canonical_match = re.search(r'<link rel="canonical"[^>]+>', html)
    if canonical_match:
        insert_at = canonical_match.end()
        return html[:insert_at] + "\n" + hreflang_tags + html[insert_at:]
    # Fallback: inject after charset meta
    charset_match = re.search(r'<meta charset="[^"]+">', html)
    if charset_match:
        insert_at = charset_match.end()
        return html[:insert_at] + "\n    " + hreflang_tags.replace('\n', '\n    ') + html[insert_at:]

    return html


# ── BreadcrumbList ──────────────────────────────────────────────────────────

def inject_breadcrumb(html: str, filepath: Path) -> str:
    if '"BreadcrumbList"' in html:
        return html

    canonical = extract_canonical(html)
    article_name = extract_article_name(html)

    schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{BASE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Blog", "item": f"{BASE_URL}/blog.html"},
            {"@type": "ListItem", "position": 3, "name": article_name, "item": canonical or (f"{BASE_URL}/blog/{filepath.name}")}
        ]
    }
    tag = f'    <!-- Schema: BreadcrumbList -->\n    <script type="application/ld+json">\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n    </script>'
    return html.replace("</head>", f"\n{tag}\n</head>", 1)


# ── Improved Byline ─────────────────────────────────────────────────────────

def inject_improved_byline(html: str) -> str:
    if 'iOS Developer, Crypto Educator' in html:
        return html

    # Replace old byline if present
    if BYLINE_SENTINEL in html:
        old = re.compile(r'<p class="article-author-byline"[^>]*>.*?</p>', re.DOTALL)
        return old.sub(IMPROVED_BYLINE, html, count=1)

    # Or insert after </h1>
    main_match = re.search(r"<main[^>]*>(.*?)</main>", html, re.DOTALL)
    if not main_match:
        return html

    main_content = main_match.group(1)
    h1_end = main_content.find('</h1>')
    if h1_end == -1:
        return html

    insert_at = main_match.start() + len('<main class="content">') + h1_end + len('</h1>')
    return html[:insert_at] + "\n                " + IMPROVED_BYLINE + html[insert_at:]


# ── FAQPage ─────────────────────────────────────────────────────────────────

def extract_faq_pairs(html: str) -> list:
    faq_match = re.search(
        r'<h2[^>]*id=["\']faq["\'][^>]*>.*?</h2>(.*?)(?=<h2|</main>|<footer)',
        html, re.DOTALL | re.IGNORECASE
    )
    if not faq_match:
        return []

    section = faq_match.group(1)
    pairs = []
    questions = list(re.finditer(r"<h3[^>]*>(.*?)</h3>(.*?)(?=<h3|$)", section, re.DOTALL))
    for q_match in questions[:6]:
        question = strip_html(q_match.group(1))
        answer_html = q_match.group(2)
        p_match = re.search(r"<p>(.*?)</p>", answer_html, re.DOTALL)
        answer = strip_html(p_match.group(1)) if p_match else strip_html(answer_html)[:500]
        if question and answer:
            pairs.append((question, answer))
    return pairs


def inject_faqpage(html: str) -> str:
    if '"FAQPage"' in html:
        return html
    pairs = extract_faq_pairs(html)
    if not pairs:
        return html

    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in pairs
        ]
    }
    tag = f'    <script type="application/ld+json">\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n    </script>'
    return html.replace("</head>", f"\n{tag}\n</head>", 1)


# ── ItemList Schema for Listicles ───────────────────────────────────────────

def is_listicle(html: str) -> bool:
    """Detect listicle / comparison / 'Best X' type posts."""
    title = extract_title(html).lower()
    h1 = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    heading = h1.group(1).lower() if h1 else title
    return bool(re.search(
        r'\b(top|best)\s+\d+|^\d+\s+(best|essential|crypto|ways|tips|reasons)'
        r'|\bvs\.?\s+\w+\b|compar(ed|ison)|alternative|review\b',
        heading
    ))


def extract_numbered_items(html: str) -> list:
    """Extract numbered H2 sections for ItemList.
    Falls back to all non-utility H2s for listicle posts without numbered headings."""
    main_match = re.search(r'<main[^>]*>(.*?)</main>', html, re.DOTALL)
    if not main_match:
        return []

    content = main_match.group(1)

    # First attempt: numbered H2s ("1.", "1 —", etc.)
    h2_matches = re.finditer(
        r'<h2[^>]*>\s*(?:<span[^>]*>[^<]*</span>\s*)?'
        r'(\d+)[\.\s)—–]+\s*'
        r'([^<]+)'
        r'</h2>',
        content
    )

    items = []
    for m in h2_matches:
        num = int(m.group(1))
        name = strip_html(m.group(2))
        id_match = re.search(r'id="([^"]+)"', m.group(0))
        anchor = id_match.group(1) if id_match else f'item-{num}'
        items.append({
            "position": num,
            "name": name,
            "url": f"{extract_canonical(html)}#{anchor}" if extract_canonical(html) else ""
        })

    if 3 <= len(items) <= 15:
        return items

    # Fallback for listicle posts without numbered H2s:
    # Extract all H2s, filter out utility headings, number by position
    SKIP_H2S = {'faq', 'frequently asked questions', 'key takeaways', 'conclusion',
                'summary', 'final thoughts', 'resources', 'references', 'disclaimer',
                'about the author', 'related posts', 'what is chartscope',
                'how chartscope helps', 'get started with chartscope',
                'comparison table', 'side-by-side comparison',
                '7 chart patterns at a glance'}

    all_h2s = re.finditer(r'<h2[^>]*>\s*(?:<span[^>]*>[^<]*</span>\s*)?([^<]+)</h2>', content)

    items = []
    pos = 0
    for m in all_h2s:
        name = strip_html(m.group(1))
        if name.lower() in SKIP_H2S:
            continue
        pos += 1
        id_match = re.search(r'id="([^"]+)"', m.group(0))
        anchor = id_match.group(1) if id_match else ''
        items.append({
            "position": pos,
            "name": name[:120],
            "url": f"{extract_canonical(html)}#{anchor}" if extract_canonical(html) and anchor else ""
        })

    if 3 <= len(items) <= 15:
        return items
    return []


def inject_itemlist(html: str) -> str:
    if '"ItemList"' in html:
        return html
    if not is_listicle(html):
        return html

    items = extract_numbered_items(html)
    if not items:
        return html

    schema = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": extract_article_name(html),
        "description": extract_description(html)[:300] if extract_description(html) else "",
        "numberOfItems": len(items),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": item["position"],
                "name": item["name"],
                "url": item["url"]
            }
            for item in items
        ]
    }

    tag = f'    <!-- Schema: ItemList -->\n    <script type="application/ld+json">\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n    </script>'
    return html.replace("</head>", f"\n{tag}\n</head>", 1)


# ── HowTo Schema for Tutorials ──────────────────────────────────────────────

def is_tutorial(html: str) -> bool:
    title = extract_title(html).lower()
    h1 = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    heading = h1.group(1).lower() if h1 else title
    return bool(re.search(r'how to|step.by.step|guide|tutorial|practice|learn|beginner', heading))


def extract_steps(html: str) -> list:
    """Extract step-by-step content from H2/H3 headings."""
    main_match = re.search(r'<main[^>]*>(.*?)</main>', html, re.DOTALL)
    if not main_match:
        return []

    content = main_match.group(1)
    steps = []

    # Find "Step X" or numbered headings that look like steps
    step_patterns = [
        r'<h[23][^>]*>\s*Step\s+(\d+)[:\s—–]*(.*?)</h[23]>',
        r'<h[23][^>]*>\s*(\d+)\.[\s]+(.*?)</h[23]>',
    ]

    for pattern in step_patterns:
        matches = list(re.finditer(pattern, content, re.IGNORECASE))
        if 2 <= len(matches) <= 10:
            for m in matches:
                pos = int(m.group(1))
                name = strip_html(m.group(2))

                # Get text after this heading until next heading
                end_of_heading = m.end()
                next_heading = re.search(r'<h[23]', content[end_of_heading:])
                text_end = end_of_heading + next_heading.start() if next_heading else end_of_heading + 500
                text = strip_html(content[end_of_heading:text_end])[:300]

                steps.append({"position": pos, "name": name, "text": text})
            break

    return steps[:8]


def inject_howto(html: str) -> str:
    if '"HowTo"' in html:
        return html
    if not is_tutorial(html):
        return html

    steps = extract_steps(html)
    if len(steps) < 2:
        return html

    schema = {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": f"How to {extract_article_name(html)}",
        "description": extract_description(html)[:300] if extract_description(html) else "",
        "step": [
            {
                "@type": "HowToStep",
                "position": s["position"],
                "name": s["name"],
                "text": s["text"]
            }
            for s in steps
        ]
    }

    tag = f'    <!-- Schema: HowTo -->\n    <script type="application/ld+json">\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n    </script>'
    return html.replace("</head>", f"\n{tag}\n</head>", 1)


# ── Article Schema Upgrade ──────────────────────────────────────────────────

def upgrade_article(html: str) -> str:
    """Add author, publisher, keywords, wordCount to Article schema."""
    if '"author"' in html and '"keywords"' in html:
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

    if "author" not in obj:
        obj["author"] = AUTHOR
    if "publisher" not in obj:
        obj["publisher"] = PUBLISHER
    if "keywords" not in obj:
        title = obj.get("headline", extract_title(html))
        desc = obj.get("description", extract_description(html))
        obj["keywords"] = extract_keywords_from_title(title, desc)
    if "wordCount" not in obj:
        obj["wordCount"] = count_words(html)
    if "inLanguage" not in obj:
        obj["inLanguage"] = "en"

    new_schema = (
        match.group(1) + "\n" +
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n" +
        match.group(3)
    )
    return html[:match.start()] + new_schema + html[match.end():]


# ── Freshness Timestamp ─────────────────────────────────────────────────────

def inject_freshness(html: str) -> str:
    """Ensure dateModified is visible in article meta."""
    if 'article:modified_time' in html:
        return html

    # Inject after article:published_time or after the last article:tag
    pub_match = re.search(r'<meta property="article:published_time"[^>]+>', html)
    if pub_match:
        insert_at = pub_match.end()
        tag = f'\n    <meta property="article:modified_time" content="{TODAY}T00:00:00+00:00">'
        return html[:insert_at] + tag + html[insert_at:]

    return html


# ── Main Processor ──────────────────────────────────────────────────────────

def process_post(filepath: Path) -> dict:
    original = filepath.read_text(encoding="utf-8")
    html = original
    changes = []

    # 1. Hreflang (most important for GEO)
    new_html = inject_hreflang(html, filepath)
    if new_html != html:
        changes.append("hreflang")
        html = new_html

    # 2. BreadcrumbList
    new_html = inject_breadcrumb(html, filepath)
    if new_html != html:
        changes.append("BreadcrumbList")
        html = new_html

    # 3. Article upgrade
    new_html = upgrade_article(html)
    if new_html != html:
        changes.append("Article enriched")
        html = new_html

    # 4. FAQPage
    new_html = inject_faqpage(html)
    if new_html != html:
        changes.append("FAQPage")
        html = new_html

    # 5. ItemList (for listicles)
    new_html = inject_itemlist(html)
    if new_html != html:
        changes.append("ItemList")
        html = new_html

    # 6. HowTo (for tutorials)
    new_html = inject_howto(html)
    if new_html != html:
        changes.append("HowTo")
        html = new_html

    # 7. Improved byline
    new_html = inject_improved_byline(html)
    if new_html != html:
        changes.append("improved byline")
        html = new_html

    # 8. Freshness
    new_html = inject_freshness(html)
    if new_html != html:
        changes.append("freshness timestamp")
        html = new_html

    if html != original:
        filepath.write_text(html, encoding="utf-8")

    return {"file": filepath.name, "changes": changes}


def main():
    print("GEO Schema Batch Upgrade\n")
    results = []

    for f in sorted(BLOG_DIR.glob("*.html")):
        r = process_post(f)
        results.append(r)
        if r["changes"]:
            print(f"  ✓ {r['file']}: {', '.join(r['changes'])}")
        else:
            print(f"  – {r['file']}: already up to date")

    total_changed = sum(1 for r in results if r["changes"])
    total_changes = sum(len(r["changes"]) for r in results)
    print(f"\n{'='*60}")
    print(f"Total: {total_changed}/{len(results)} posts updated ({total_changes} changes)")

    # Summary by change type
    from collections import Counter
    change_counts = Counter()
    for r in results:
        for c in r["changes"]:
            change_counts[c] += 1

    print("\nChanges by type:")
    for change, count in change_counts.most_common():
        print(f"  {change}: {count}")


if __name__ == "__main__":
    main()
