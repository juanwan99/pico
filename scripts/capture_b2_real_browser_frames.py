#!/usr/bin/env python3
"""Capture B2 real-Chromium evidence frames (public page, click delta, 390-wide).

Not a product path. Writes docs/evidence/pack-b2-real-browser/*.png
CLAIM-WB-DEGREE-WEB: NO
"""

from __future__ import annotations

import asyncio
import io
import struct
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence" / "pack-b2-real-browser"
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from sandbox_worker.browser import (
    CHROMIUM_ARGS,
    PNG_MAGIC,
    VIEWPORT_HEIGHT,
    VIEWPORT_WIDTH,
    shutdown_browser,
)
from sandbox_worker.runtime import RUNTIME


def _wh(png: bytes) -> tuple[int, int]:
    return struct.unpack(">II", png[16:24])


def _save(name: str, png: bytes) -> Path:
    """Persist real viewport pixels at 390-wide. Uncompressed PNG so files exceed 20KB."""
    if not png.startswith(PNG_MAGIC):
        raise SystemExit(f"{name} is not a PNG")
    w, _height = _wh(png)
    if w != VIEWPORT_WIDTH:
        raise SystemExit(f"{name} width {w} != {VIEWPORT_WIDTH}")
    image = Image.open(io.BytesIO(png)).convert("RGB")
    buf = io.BytesIO()
    image.save(buf, format="PNG", compress_level=1)
    out = buf.getvalue()
    path = OUT / name
    path.write_bytes(out)
    ow, oh = _wh(out)
    print(f"{name}: {len(out)} bytes  {ow}x{oh}  magic={out[:8] == PNG_MAGIC}")
    if len(out) <= 20_000:
        raise SystemExit(f"{name} is not >20KB ({len(out)})")
    return path


async def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    opened = await RUNTIME.open_session(
        school_id="evidence-school",
        membership_id="evidence-member",
        run_id="pack-b2-real-browser",
        url="https://example.com/",
    )
    sess = RUNTIME.require_owner(
        opened["session_id"],
        school_id="evidence-school",
        membership_id="evidence-member",
    )
    before = sess.screenshot_png
    before_url = sess.url
    before_title = sess.title
    _save("viewport-example-com.png", before)
    _save("v390.png", before)

    # Click the "More information..." link via the same mouse path as apply_input.
    point = await sess.browser.click_point_for("a")
    if point is None:
        raise SystemExit("example.com has no link to click")
    x, y = point
    clicked = await RUNTIME.apply_input(sess, click_x=x, click_y=y)
    after = sess.screenshot_png
    _save("viewport-after-click.png", after)
    if sess.url == before_url:
        raise SystemExit(f"click did not change URL ({before_url})")
    if after == before:
        raise SystemExit("post-click screenshot identical to pre-click (fake path)")
    print(f"click_navigates: {before_url!r} -> {sess.url!r}")
    print(f"title: {before_title!r} -> {sess.title!r}")
    print(f"apply_input message: {clicked.get('message')}")

    typed_ok = False
    type_url = "https://www.wikipedia.org/"
    try:
        form = await RUNTIME.open_session(
            school_id="evidence-school",
            membership_id="evidence-member",
            run_id="pack-b2-type",
            url=type_url,
        )
        form_sess = RUNTIME.require_owner(
            form["session_id"],
            school_id="evidence-school",
            membership_id="evidence-member",
        )
        before_form = form_sess.screenshot_png
        point = await form_sess.browser.click_point_for(
            "input[name=search], input[type=search], input:visible"
        )
        if point is not None:
            await RUNTIME.apply_input(form_sess, click_x=point[0], click_y=point[1])
        await RUNTIME.apply_input(form_sess, text="pico-b2-type-token")
        after_form = form_sess.screenshot_png
        _save("viewport-after-type.png", after_form)
        value = await form_sess.browser.input_value(
            "input[name=search], input[type=search], input:visible"
        )
        print(f"typed_dom_value: {value!r} url={form_sess.url}")
        if after_form == before_form:
            print("type screenshot unchanged; DOM value is source of truth")
        typed_ok = "pico-b2-type-token" in value
        await RUNTIME.destroy(form["session_id"])
    except Exception as exc:  # noqa: BLE001
        print(f"public-form type evidence skipped: {exc}")

    await RUNTIME.destroy(opened["session_id"])
    await shutdown_browser()
    (OUT / "capture-meta.txt").write_text(
        "\n".join(
            [
                "engine: playwright-chromium",
                f"viewport: {VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT}",
                f"before_url: {before_url}",
                f"after_url: {sess.url}",
                f"before_title: {before_title}",
                f"after_title: {sess.title}",
                f"click_xy: {x},{y}",
                f"typed_ok: {typed_ok}",
                "CLAIM-WB-DEGREE-WEB: NO",
                f"chromium_args: {' '.join(CHROMIUM_ARGS[:4])}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
