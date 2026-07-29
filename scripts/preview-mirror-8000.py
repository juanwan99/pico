#!/usr/bin/env python3
"""Public :8000 → NextChat :8080 (preview often sticks to :8000)."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import http.client
from urllib.parse import urlsplit

UP_HOST, UP_PORT = "127.0.0.1", 8080

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass

    def do_REQUEST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        path = self.path
        conn = http.client.HTTPConnection(UP_HOST, UP_PORT, timeout=300)
        headers = {}
        for k, v in self.headers.items():
            kl = k.lower()
            if kl in ("host", "transfer-encoding", "connection"):
                continue
            headers[k] = v
        headers["Host"] = f"{UP_HOST}:{UP_PORT}"
        headers["Accept-Encoding"] = "identity"
        try:
            conn.request(self.command, path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                kl = k.lower()
                if kl in ("transfer-encoding", "connection", "content-length"):
                    continue
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            msg = (
                "<!doctype html><meta charset=utf-8><title>Pico</title>"
                f"<body style='font-family:sans-serif;padding:2rem'>"
                f"<h1>Pico 工作台启动中</h1><p>{e}</p>"
                f"<p>请稍后刷新预览。</p></body>"
            ).encode()
            self.send_response(502)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
        finally:
            conn.close()

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_HEAD = do_REQUEST

if __name__ == "__main__":
    print("mirror 0.0.0.0:8000 -> 127.0.0.1:8080", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
