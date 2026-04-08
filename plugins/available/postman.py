"""Postman — curl proxy. CORS bypass for browser fetch.

fetch('/proxy/postman', {method:'POST', body: JSON.stringify({url:'https://api.github.com/repos/x/y'})})

Requires approve token. Because this is curl with your server's IP.
"""
import json, subprocess

DESCRIPTION = "curl proxy — CORS bypass, approve-token only"
ROUTES = {}


async def handle_postman(method, body, params):
    b = json.loads(body) if body else {}
    url = b.get("url", "")
    if not url or not url.startswith(("http://", "https://")):
        return {"error": "url required (http/https)", "_status": 400}
    cmd = ["curl", "-s", "-m", "30", "-X", b.get("method", "GET").upper()]
    for k, v in b.get("headers", {}).items():
        cmd += ["-H", f"{k}: {v}"]
    if b.get("body"):
        cmd += ["-d", b["body"]]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, timeout=35)
    return {"_html": r.stdout.decode("utf-8", "replace"), "_status": 200}


ROUTES["/proxy/postman"] = handle_postman
