#!/usr/bin/env python3
"""
Webhook listener
При создании платежа стоит указать http://host.docker.internal:9000 как webhook_url.
Так контейнер consumer сможет достучаться до listener-а на хосте.
"""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
            print(json.dumps(data, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(body.decode())
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[webhook] {args[0]}")


def main():
    url = os.environ.get("WEBHOOK_URL", "http://0.0.0.0:9000")
    host, port = url.rsplit(":", 1)
    port = int(port.rstrip("/"))
    host = host.split("//")[-1]
    server = HTTPServer((host, int(port)), WebhookHandler)
    print(f"Webhook listener running on {host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
