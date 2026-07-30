#!/usr/bin/env python3
"""Public preview entry :8080 → NextChat UI; /v1 /health → Pico API (loopback)."""
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UI = "http://127.0.0.1:3000"
API = "http://127.0.0.1:8000"

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a):
        pass
    def _base(self):
        path = self.path.split("?", 1)[0]
        if path == "/health" or path.startswith(("/v1", "/docs", "/openapi", "/redoc")):
            return API
        return UI
    def do_REQUEST(self):
        url = self._base() + self.path
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(url, data=body, method=self.command)
        for k, v in self.headers.items():
            if k.lower() in ("host", "transfer-encoding", "connection", "content-length"):
                continue
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in ("transfer-encoding", "connection", "content-encoding"):
                        continue
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", e.headers.get("Content-Type", "text/plain"))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:  # noqa: BLE001
            msg = ('{"ok":false,"error":"' + str(e).replace('"', '') + '"}').encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_REQUEST

if __name__ == "__main__":
    print("gateway 0.0.0.0:8080 -> ui:3000 api:8000", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8080), H).serve_forever()
