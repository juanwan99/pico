"""LC3: single-file roll-call + countdown page, driven in headless Chromium."""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, "/w/check")
from _common import OUT, Score

NAMES = ["张三", "李四", "王五", "赵六", "孙七"]


def page_path():
    found = []
    for dirpath, _dirs, files in os.walk(OUT):
        found += [os.path.join(dirpath, f) for f in files if f.lower().endswith((".html", ".htm"))]
    return min(found, key=len) if found else None


def picked(text):
    hits = [n for n in NAMES if n in (text or "")]
    return hits[0] if len(hits) == 1 else None


def settled(page, sel, quiet_ms=600, max_ms=5000):
    """Text of ``sel`` once it stops changing: pages may roll names before landing."""
    last, still, waited = None, 0, 0
    while waited < max_ms:
        now = page.text_content(sel)
        still = still + 100 if now == last else 0
        if still >= quiet_ms:
            break
        last = now
        page.wait_for_timeout(100)
        waited += 100
    return last


def main():
    sc = Score()
    path = page_path()
    if not path:
        sc.fail("no .html delivered")
        sc.emit()
    html = Path(path).read_text(encoding="utf-8", errors="replace")
    sc.check(
        not re.search(r"""(src|href)\s*=\s*["']?(https?:)?//""", html, re.IGNORECASE),
        "page loads external assets",
    )
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)[:120]))
        page.goto("file://" + path)
        page.wait_for_timeout(300)
        try:
            page.fill("#names", "\n".join(NAMES))
            got = []
            for _ in NAMES:
                page.click("#pick")
                got.append(picked(settled(page, "#result")))
            sc.check(
                sorted(n for n in got if n) == sorted(NAMES),
                f"5 picks should cover all 5 once, got {got}",
            )
            page.click("#pick")
            sc.check(
                picked(settled(page, "#result")) is not None,
                "6th pick (new round) shows no name",
                essential=False,
            )
        except Exception as exc:  # noqa: BLE001
            sc.fail(f"roll call: {type(exc).__name__}: {str(exc)[:120]}")
        try:
            page.fill("#minutes", "1")
            page.click("#start")
            page.wait_for_timeout(2600)
            shown = (page.text_content("#timer") or "").strip()
            sc.check(
                bool(re.fullmatch(r"0?0:5[6-8]", shown)),
                f"timer after ~2.6s of 1 minute shows {shown!r}, want 00:57",
            )
        except Exception as exc:  # noqa: BLE001
            sc.fail(f"timer: {type(exc).__name__}: {str(exc)[:120]}")
        sc.check(not errors, "page errors: " + "; ".join(errors[:3]))
        browser.close()
    sc.emit()


main()
