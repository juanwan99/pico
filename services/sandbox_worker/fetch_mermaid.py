"""Download pinned mermaid.min.js at image build. Fail closed if every mirror misses."""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SERVICES = Path(__file__).resolve().parents[1]
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

from sandbox_worker.mermaid_pin import (
    MERMAID_MAX_BYTES,
    MERMAID_MIN_BYTES,
    MERMAID_URLS,
    MERMAID_VERSION,
)


def download_mermaid(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error = "no mirrors"
    for url in MERMAID_URLS:
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                raw = resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = f"{url}: {exc}"
            continue
        if not (MERMAID_MIN_BYTES <= len(raw) <= MERMAID_MAX_BYTES):
            last_error = f"{url}: unexpected size {len(raw)}"
            continue
        if b"mermaid" not in raw[:8000].lower() and b"Mermaid" not in raw[:8000]:
            # UMD header usually mentions mermaid; reject HTML error pages.
            head = raw[:200].lstrip()
            if head.startswith((b"<", b"{")):
                last_error = f"{url}: not a mermaid UMD bundle"
                continue
        dest.write_bytes(raw)
        return dest
    raise SystemExit(
        f"failed to fetch mermaid@{MERMAID_VERSION} ({last_error})"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch pinned mermaid.min.js")
    parser.add_argument("--dest", required=True)
    args = parser.parse_args(argv)
    path = download_mermaid(Path(args.dest))
    print(f"wrote mermaid@{MERMAID_VERSION} -> {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
