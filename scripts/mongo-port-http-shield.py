#!/usr/bin/env python3
"""HTTP shield on :27017 — mis-pinned Live Preview hits this instead of Mongo wire protocol.

Mongo lives on 27117. Preview discovery often probes 27017; native mongod answers with
'It looks like you are trying to access MongoDB over HTTP…'. Forward HTTP to product UI.
"""
from __future__ import annotations

import http.client
import socketserver
import sys
from http.server import BaseHTTPRequestHandler

UPSTREAM_HOST = "127.0.0.1"
UPSTREAM_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
LISTEN_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 27017


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:  # quieter
        sys.stderr.write("[27017-shield] " + (fmt % args) + "\n")

    def _proxy(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        path = self.path
        try:
            conn = http.client.HTTPConnection(UPSTREAM_HOST, UPSTREAM_PORT, timeout=30)
            headers = {k: v for k, v in self.headers.items() if k.lower() not in {"host", "connection"}}
            headers["Host"] = f"{UPSTREAM_HOST}:{UPSTREAM_PORT}"
            headers["Connection"] = "close"
            conn.request(self.command, path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            self.send_response(resp.status, resp.reason)
            for k, v in resp.getheaders():
                if k.lower() in {"transfer-encoding", "connection", "content-encoding"}:
                    continue
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            # help human realize this was a shield hit
            self.send_header("X-Pico-Preview-Shield", "27017->8080")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)
            conn.close()
        except Exception as e:
            msg = (
                "<!doctype html><meta charset=utf-8><title>Pico</title>"
                "<p>预览误打到数据库端口，正在尝试回跳产品页失败。</p>"
                f"<p><a href='http://127.0.0.1:{UPSTREAM_PORT}/'>打开产品</a></p>"
                f"<pre>{e}</pre>"
            ).encode()
            self.send_response(502)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

    def do_GET(self) -> None:
        self._proxy()

    def do_HEAD(self) -> None:
        self._proxy()

    def do_POST(self) -> None:
        self._proxy()

    def do_PUT(self) -> None:
        self._proxy()

    def do_DELETE(self) -> None:
        self._proxy()

    def do_OPTIONS(self) -> None:
        self._proxy()

    def do_PATCH(self) -> None:
        self._proxy()


class ReuseTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


def main() -> None:
    with ReuseTCPServer(("0.0.0.0", LISTEN_PORT), Handler) as httpd:
        sys.stderr.write(f"[27017-shield] listening 0.0.0.0:{LISTEN_PORT} → {UPSTREAM_HOST}:{UPSTREAM_PORT}\n")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
