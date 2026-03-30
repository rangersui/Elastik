"""Postman plugin — raw HTTP with full headers.

Install: lucy install postman
Requires approve token. Returns complete response including headers.

Configure ALLOWED_HOSTS before use. Empty = block all.
"""

import json
import os
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

DESCRIPTION = "Raw HTTP gateway — full headers, whitelist-only"
ROUTES = {}

# Comma-separated hostnames. Empty = block all.
# e.g. POSTMAN_HOSTS=httpbin.org,api.github.com
ALLOWED_HOSTS = [h.strip() for h in os.getenv("POSTMAN_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

PARAMS_SCHEMA = {
    "/proxy/postman": {
        "method": "POST",
        "params": {
            "url": {"type": "string", "required": True, "description": "Full URL"},
            "method": {"type": "string", "required": False, "description": "HTTP method (default GET)"},
            "headers": {"type": "object", "required": False, "description": "Request headers"},
            "body": {"type": "string", "required": False, "description": "Request body"},
        },
        "example": {"url": "https://httpbin.org/get", "method": "GET"},
        "returns": {"status": "int", "headers": "object", "body": "string"}
    },
}


async def handle_postman(method, body, params):
    b = json.loads(body) if body else {}
    url = params.get("url") or b.get("url", "")
    if not url:
        return {"error": "url required"}
    host = urlparse(url).hostname or ""
    if not ALLOWED_HOSTS:
        return {"error": "no allowed hosts configured. Set POSTMAN_HOSTS env var"}
    if host not in ALLOWED_HOSTS:
        return {"error": f"host '{host}' not in whitelist", "allowed": ALLOWED_HOSTS}
    req_method = (params.get("method") or b.get("method", "GET")).upper()
    req_headers = b.get("headers", {})
    req_body = (b.get("body") or "").encode("utf-8") or None

    req = Request(url, data=req_body, headers=req_headers, method=req_method)
    try:
        r = urlopen(req, timeout=30)
        return {
            "status": r.status,
            "headers": dict(r.headers),
            "body": r.read().decode("utf-8", "replace"),
        }
    except HTTPError as e:
        return {
            "status": e.code,
            "headers": dict(e.headers),
            "body": e.read().decode("utf-8", "replace"),
        }
    except URLError as e:
        return {"error": str(e.reason)}


ROUTES["/proxy/postman"] = handle_postman
