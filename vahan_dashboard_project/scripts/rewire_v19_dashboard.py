#!/usr/bin/env python3
"""Take the archived v18 dashboard HTML, splice in the new payloads, and
write a single-file v19 dashboard at the project root.

Differences from v18:
  - Inline <script id="payload"> JSON replaced by outputs/dashboard_payload.json
  - External <script src="state_payload.js"> replaced by an inline
    <script>window.__STATE_PAYLOAD__ = {...};</script> block so the dashboard
    is now truly single-file.
  - Title bumped to v19.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_HTML = ROOT / "archive" / "legacy_pre_standardization_20260530" / "vahan_dashboard_v18.html"
INLINE_PAYLOAD = ROOT / "outputs" / "dashboard_payload.json"
STATE_PAYLOAD = ROOT / "outputs" / "dashboard_state_payload.json"
TARGET_HTML = ROOT / "vahan_dashboard_v19.html"

PAYLOAD_TAG_RE = re.compile(
    r'(<script id="payload" type="application/json">)(.*?)(</script>)',
    re.DOTALL,
)
STATE_SRC_RE = re.compile(r'<script src="state_payload\.js"></script>')
# Match the already-inlined state-payload block so we can update it in place
# on subsequent runs (when sourcing from the existing v19).
STATE_INLINE_RE = re.compile(
    r'<script>window\.__STATE_PAYLOAD__ = (.*?);</script>',
    re.DOTALL,
)


def main():
    # If a v19 already exists at root, source from it so accumulated JS/CSS
    # edits to the active dashboard are preserved across data refreshes.
    # Otherwise fall back to the archived v18 template for a clean rebuild.
    if TARGET_HTML.exists():
        print(f"Reading existing v19 (preserves in-place edits): {TARGET_HTML}")
        html = TARGET_HTML.read_text(encoding="utf-8")
    else:
        print(f"Reading source v18 template from archive: {SOURCE_HTML}")
        html = SOURCE_HTML.read_text(encoding="utf-8")
    print(f"  size: {len(html):,} bytes")

    print(f"Loading inline payload: {INLINE_PAYLOAD}")
    inline_json = INLINE_PAYLOAD.read_text(encoding="utf-8")
    print(f"  size: {len(inline_json):,} bytes")

    print(f"Loading state payload: {STATE_PAYLOAD}")
    state_json = STATE_PAYLOAD.read_text(encoding="utf-8")
    print(f"  size: {len(state_json):,} bytes")

    # 1. Replace the inline <script id="payload"> body
    m = PAYLOAD_TAG_RE.search(html)
    if not m:
        raise SystemExit("Could not find <script id='payload'> in source HTML")
    new_html = html[:m.start(2)] + inline_json + html[m.end(2):]

    # 2. Replace either the external state_payload.js script tag (first run,
    # sourcing from v18 archive) or the already-inlined state-payload block
    # (subsequent runs, sourcing from existing v19) with the new payload.
    inline_state = (
        '<script>window.__STATE_PAYLOAD__ = '
        + state_json
        + ';</script>'
    )
    if STATE_SRC_RE.search(new_html):
        new_html = STATE_SRC_RE.sub(inline_state, new_html)
        print("  replaced external <script src=state_payload.js> with inline block")
    elif STATE_INLINE_RE.search(new_html):
        new_html = STATE_INLINE_RE.sub(inline_state, new_html, count=1)
        print("  updated existing inline state-payload block")
    else:
        raise SystemExit("Could not find state-payload script in source HTML")

    # 3. Bump title to v19
    new_html = new_html.replace(
        "India · VAHAN dashboard 2021–2026 · v18 · 24mo panel promoted",
        "India · VAHAN dashboard 2021–2026 · v19 · canonical-data rewire",
    )

    print(f"Writing {TARGET_HTML}")
    tmp = TARGET_HTML.with_suffix(TARGET_HTML.suffix + ".tmp")
    tmp.write_text(new_html, encoding="utf-8")
    tmp.replace(TARGET_HTML)
    print(f"  size: {len(new_html):,} bytes")
    print("Done.")


if __name__ == "__main__":
    main()
