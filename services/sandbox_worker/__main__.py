"""Run: python -m sandbox_worker"""

from __future__ import annotations

import os

from sandbox_worker.ports import SANDBOX_DEFAULT_PORT, assert_listen_port


def main() -> None:
    import uvicorn

    host = (os.environ.get("PICO_SANDBOX_HOST") or "0.0.0.0").strip() or "0.0.0.0"
    port = assert_listen_port(int(os.environ.get("PICO_SANDBOX_PORT") or SANDBOX_DEFAULT_PORT))
    uvicorn.run(
        "sandbox_worker.app:app",
        host=host,
        port=port,
        factory=False,
    )


if __name__ == "__main__":
    main()
