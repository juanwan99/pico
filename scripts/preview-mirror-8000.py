#!/usr/bin/env python3
"""Public :8000 and used for sticky preview → LibreChat :3080."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import http.client
UP_HOST, UP_PORT = "127.0.0.1", 3080
class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def do_REQUEST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        conn = http.client.HTTPConnection(UP_HOST, UP_PORT, timeout=300)
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in ("host", "transfer-encoding", "connection")}
        headers["Host"] = f"{UP_HOST}:{UP_PORT}"
        headers["Accept-Encoding"] = "identity"
        try:
            conn.request(self.command, self.path, body=body, headers=headers)
            resp = conn.getresponse(); data = resp.read()
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() in ("transfer-encoding", "connection", "content-length"): continue
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD": self.wfile.write(data)
        except Exception as e:
            msg = f"<!doctype html><meta charset=utf-8><h1>Pico</h1><pre>{e}</pre>".encode()
            self.send_response(502); self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(msg))); self.end_headers(); self.wfile.write(msg)
        finally: conn.close()
    do_GET=do_POST=do_PUT=do_PATCH=do_DELETE=do_OPTIONS=do_HEAD=do_REQUEST
if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv)>1 else 8000
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
