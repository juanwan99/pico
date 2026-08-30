"""OpenAI-compatible /v1/chat/completions for LibreChat and API clients."""
from __future__ import annotations

import base64
import gzip
from pathlib import Path

_p = Path(__file__).resolve().parent
_blob = "".join(
    (_p / f"_oc_p{i:02d}.b64").read_text(encoding="ascii")
    for i in range(11)
)
_src = gzip.decompress(base64.b64decode("".join(_blob.split()))).decode("utf-8")
exec(compile(_src, __file__, "exec"), globals())
