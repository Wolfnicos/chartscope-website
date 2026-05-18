#!/usr/bin/env python3
"""
Add/upgrade CTAs across all blog posts for chartscope.net.

Changes applied to ALL 40 posts:
  - Add "Get the App" button to nav
  - Fix © 2025 -> © 2026 in footer

Additional changes for SignalLens-generated posts (no existing cta-box style):
  - Add mid-article CTA block after 3rd content H2
  - Replace Continue Learning section with styled app CTA + keep related links

For the 4 well-built posts (existing cta-box style):
  - Add download button to Continue Learning highlight-box
"""

import os
import re
from pathlib import Path

BLOG_DIR = Path("/Users/lupudragos/ChartScope/chartscope-website/blog")
APP_URL = "https://apps.apple.com/app/chartscope/id6757865711"

# Sentinel to detect if nav button already injected
NAV_SENTINEL = "nav-cta-btn"

NAV_CSS = """        .nav-cta-btn {
            background: var(--accent-blue);
            color: #fff !important;
            padding: 8px 18px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9rem;
            text-decoration: none;
            transition: opacity 0.2s, transform 0.2s;
            white-space: nowrap;
        }
        .nav-cta-btn:hover {
            opacity: 0.85;
            transform: scale(1.02);
            color: #fff !important;
        }
"""

NAV_BUTTON_LI = f'                <li><a href="{APP_URL}" class="nav-cta-btn">Get the App</a></li>'

MID_ARTICLE_CTA = f"""
<div style="background:linear-gradient(135deg,rgba(10,132,255,0.1) 0%,rgba(191,90,242,0.1) 100%);border:1px solid rgba(10,132,255,0.25);border-radius:16px;padding:28px 24px;margin:44px 0;text-align:center;">
    <p style="font-size:1.05rem;font-weight:600;margin-bottom:8px;color:#fff;">Learn faster with AI-powered chart explanations</p>
    <p style="margin-bottom:20px;color:rgba(255,255,255,0.7);font-size:0.95rem;">ChartScope explains every indicator, pattern, and signal on your charts — in plain language, on your iPhone. On-device ML. 9 languages. No trading signals.</p>
    <a href="{APP_URL}" style="display:inline-block;padding:12px 28px;background:#0A84FF;color:#fff;text-decoration:none;border-radius:12px;font-weight:600;font-size:1rem;">Try ChartScope Free for 3 Days →</a>
</div>
"""

def make_end_cta(related_links_html: str) -> str:
    return f"""<div style="background:linear-gradient(135deg,rgba(10,132,255,0.12) 0%,rgba(191,90,242,0.12) 100%);border:1px solid rgba(10,132,255,0.3);border-radius:20px;padding:36px 28px;margin:48px 0 32px;text-align:center;">
    <p style="font-size:1.15rem;font-weight:700;margin-bottom:12px;color:#fff;">Ready to understand your crypto charts — not just stare at them?</p>
    <ul style="list-style:none;padding:0;margin:0 0 24px;text-align:left;display:inline-block;">
        <li style="color:rgba(255,255,255,0.85);margin-bottom:8px;">&#10003;&nbsp; AI explanations for every indicator &amp; pattern</li>
        <li style="color:rgba(255,255,255,0.85);margin-bottom:8px;">&#10003;&nbsp; On-device ML — your data never leaves your iPhone</li>
        <li style="color:rgba(255,255,255,0.85);margin-bottom:8px;">&#10003;&nbsp; 9 languages · No trading signals · No financial advice</li>
    </ul>
    <br>
    <a href="{APP_URL}" style="display:inline-block;padding:14px 32px;background:#0A84FF;color:#fff;text-decoration:none;border-radius:14px;font-weight:700;font-size:1.05rem;">Download on the App Store — Free 3-Day Trial</a>
    <p style="margin-top:12px;font-size:0.85rem;color:rgba(255,255,255,0.5);">&#8364;4.99/month after trial &middot; Cancel anytime</p>
</div>

<div style="margin:32px 0 24px;">
    <p style="font-weight:600;font-size:0.95rem;margin-bottom:12px;color:rgba(255,255,255,0.6);text-transform:uppercase;letter-spacing:0.05em;">Keep Reading</p>
    {related_links_html}
</div>
"""


def add_nav_button(html: str) -> str:
    """Inject Get the App button into nav-links if not already present."""
    if NAV_SENTINEL in html:
        return html

    # Add CSS before </style> (first occurrence in blog posts)
    html = html.replace("        .content {", NAV_CSS + "        .content {", 1)
    # If .content not found, insert before </style>
    if NAV_SENTINEL not in html:
        html = html.replace("</style>", NAV_CSS + "\n        </style>", 1)

    # Add button after </li> for Support (last nav item)
    nav_pattern = r'(<li><a href="[^"]*support\.html">Support</a></li>)'
    html = re.sub(nav_pattern, r'\1\n' + NAV_BUTTON_LI, html)
    return html


def fix_footer_year(html: str) -> str:
    return html.replace("&copy; 2025 ChartScope", "&copy; 2026 ChartScope")


def is_well_built(html: str) -> bool:
    return "class=\"cta-box\"" in html or "class=\"cta-button\"" in html


def add_mid_article_cta(html: str) -> str:
    """Insert mid-article CTA after the 3rd content H2 (excluding Continue Learning)."""
    if MID_ARTICLE_CTA.strip()[:50] in html:
        return html  # already injected

    # Find all H2 positions that are not "continue-learning"
    pattern = re.compile(r'<h2(?![^>]*id="continue-learning")[^>]*>.*?</h2>', re.IGNORECASE)
    matches = list(pattern.finditer(html))

    if len(matches) >= 3:
        insert_after = matches[2].end()
    elif len(matches) >= 2:
        insert_after = matches[1].end()
    elif len(matches) >= 1:
        insert_after = matches[0].end()
    else:
        return html  # no H2 to anchor on

    return html[:insert_after] + "\n" + MID_ARTICLE_CTA + html[insert_after:]


def upgrade_continue_learning_signallens(html: str) -> str:
    """
    Replace:
      <h2 id="continue-learning">Continue Learning</h2>
      <ul>...</ul>
    with styled app CTA + keep related links.
    """
    pattern = re.compile(
        r'<h2[^>]*id="continue-learning"[^>]*>.*?</h2>\s*<ul>(.*?)</ul>',
        re.DOTALL | re.IGNORECASE
    )
    match = pattern.search(html)
    if not match:
        return html

    # Extract the existing <li> items
    existing_ul_content = match.group(1)
    # Re-style the links for Keep Reading section
    links_html = f'<ul style="list-style:none;padding:0;">{existing_ul_content}</ul>'

    replacement = make_end_cta(links_html)
    return html[:match.start()] + replacement + html[match.end():]


def upgrade_continue_learning_wellbuilt(html: str) -> str:
    """
    Add a download button inside the highlight-box Continue Learning section
    for the 4 well-built posts that already have styled CTAs.
    """
    # These posts already have a good end CTA before Continue Learning.
    # Just add a download button after the Continue Learning list.
    pattern = re.compile(
        r'(<div class="highlight-box"[^>]*>.*?<h3[^>]*>Continue Learning</h3>.*?</ul>)',
        re.DOTALL
    )
    match = pattern.search(html)
    if not match:
        return html

    download_btn = f'\n            <div style="margin-top:20px;text-align:center;"><a href="{APP_URL}" style="display:inline-block;padding:12px 28px;background:#0A84FF;color:#fff;text-decoration:none;border-radius:12px;font-weight:600;font-size:0.95rem;">Get ChartScope on the App Store →</a></div>'
    return html[:match.end()] + download_btn + html[match.end():]


def process_file(filepath: Path) -> tuple[bool, str]:
    original = filepath.read_text(encoding="utf-8")
    html = original

    html = add_nav_button(html)
    html = fix_footer_year(html)

    if is_well_built(html):
        html = upgrade_continue_learning_wellbuilt(html)
    else:
        html = add_mid_article_cta(html)
        html = upgrade_continue_learning_signallens(html)

    if html != original:
        filepath.write_text(html, encoding="utf-8")
        return True, "updated"
    return False, "no changes"


def main():
    files = sorted(BLOG_DIR.glob("*.html"))
    updated = 0
    skipped = 0
    for f in files:
        changed, reason = process_file(f)
        status = "✓" if changed else "–"
        print(f"  {status} {f.name} ({reason})")
        if changed:
            updated += 1
        else:
            skipped += 1
    print(f"\nDone: {updated} updated, {skipped} unchanged out of {len(files)} files.")


if __name__ == "__main__":
    main()
