#!/usr/bin/env python3
"""Fault-injecting relay in front of New API, for pico#1336 only (throwaway stacks).

    python3 scripts/pico-fault-upstream.py --listen 127.0.0.1:18807 \
        --target http://127.0.0.1:3000 --state <dir>/fault.json --log <dir>/fault.jsonl

Every request is forwarded to --target unchanged, except: when the state file says
{"mode": "502" | "429" | "suspended", "head": "<model id>"} and the request body's
"model" is that head model, the relay answers with that failure instead (the same
body shapes New API sends). Other models pass through, so the backup can answer.
The state file is re-read per request, so the check flips modes without a restart.
Pico recognises New API by "127.0.0.1:3000" in DEEPSEEK_BASE_URL, so the stack points
at http://127.0.0.1:<port>/127.0.0.1:3000/v1 (same code path as live); the relay drops
that path prefix before forwarding.
Stdlib only; one line per request goes to --log.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FAULTS: dict[str, tuple[int, dict]] = {
    "502": (502, {"error": {"message": "upstream 502: bad gateway", "type": "new_api_error", "code": "bad_response_status_code"}}),
    "429": (429, {"error": {"message": "当前分组上游负载已饱和，请稍后再试", "type": "new_api_error", "code": "rate_limit_exceeded"}}),
    "suspended": (403, {"error": {"message": "API密钥已被暂停，请联系管理员", "type": "permission_error", "param": "", "code": ""}}),
}
PREFIX = "/127.0.0.1:3000"
HOP = {"host", "content-length", "connection", "transfer-encoding", "keep-alive", "accept-encoding"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--log", required=True)
    args = ap.parse_args()
    host, port = args.listen.rsplit(":", 1)
    target = args.target.rstrip("/")
    state_path, log_path = Path(args.state), Path(args.log)

    def state() -> dict:
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def log(row: dict) -> None:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"t": round(time.time(), 3), **row}, ensure_ascii=False) + "\n")

    class Relay(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_a) -> None:
            return

        def _send(self, status: int, body: bytes, ctype: str = "application/json") -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

        def _relay(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            model = ""
            try:
                model = str(json.loads(body or b"{}").get("model") or "")
            except ValueError:
                pass
            st = state()
            bare = model.split("/")[-1]
            mode = str(st.get("mode") or "off")
            if mode in FAULTS and bare and bare == str(st.get("head") or ""):
                status, payload = FAULTS[mode]
                log({"model": bare, "action": f"inject_{mode}", "path": self.path})
                self._send(status, json.dumps(payload, ensure_ascii=False).encode())
                return
            path = self.path.removeprefix(PREFIX)
            req = urllib.request.Request(target + path, data=body or None, method=self.command)
            for k, v in self.headers.items():
                if k.lower() not in HOP:
                    req.add_header(k, v)
            try:
                resp = urllib.request.urlopen(req, timeout=600)
            except urllib.error.HTTPError as exc:
                log({"model": bare, "action": f"upstream_{exc.code}", "path": self.path})
                self._send(exc.code, exc.read(), exc.headers.get("Content-Type") or "application/json")
                return
            except OSError as exc:
                log({"model": bare, "action": "upstream_unreachable", "err": type(exc).__name__})
                self._send(502, b'{"error":{"message":"relay: upstream unreachable"}}')
                return
            log({"model": bare, "action": "forward", "status": resp.status, "path": self.path})
            self.send_response(resp.status)
            for k, v in resp.headers.items():
                if k.lower() not in HOP:
                    self.send_header(k, v)
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            try:
                while True:
                    chunk = resp.read1(65536) if hasattr(resp, "read1") else resp.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                log({"model": bare, "action": "client_closed"})  # hedge loser cancelled

        do_POST = _relay
        do_GET = _relay

    ThreadingHTTPServer((host, int(port)), Relay).serve_forever()


if __name__ == "__main__":
    main()
