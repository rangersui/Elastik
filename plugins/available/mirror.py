"""Mirror — reverse proxy any URL behind approve auth.

/mirror?url=https://example.com/x  → entry point
/m/example.com/x                   → subsequent navigation (same namespace)
"""
DESCRIPTION = "Reverse-proxy mirror. /mirror?url=X entry, /m/domain/path follow-up."
AUTH = "approve"
import json, re, subprocess
import server

def _load_mirror_ui():
    try:
        c = server.conn("mirror-ui")
        r = c.execute("SELECT stage_html FROM stage_meta WHERE id=1").fetchone()
        html = r["stage_html"] or ""
        if isinstance(html, bytes): html = html.decode("utf-8", "replace")
        return html
    except Exception:
        return ""


def _proxy(target, domain=""):
    """curl target, return (body_bytes, content_type). Injects <base> for HTML."""
    try:
        r = subprocess.run(["curl", "-s", "-L", "-m", "30", "-D", "-", target],
                           capture_output=True, timeout=35)
        raw = r.stdout
        sep = raw.rfind(b"\r\n\r\n")
        if sep == -1: sep = raw.rfind(b"\n\n")
        if sep == -1: return raw, "text/html"
        headers_part = raw[:sep].decode("utf-8", "replace").lower()
        body = raw[sep+4:] if raw[sep:sep+4] == b"\r\n\r\n" else raw[sep+2:]
        ct = "text/html"
        for line in headers_part.split("\n"):
            if line.strip().startswith("content-type:"):
                ct = line.split(":", 1)[1].strip()
                break
        if "text/html" in ct and domain:
            body = re.sub(rb'(?i)<meta[^>]*(?:content-security-policy|x-frame-options)[^>]*>', b'', body)
            body = f'<base href="/m/{domain}/">'.encode() + body
        return body, ct
    except Exception as e:
        return json.dumps({"error": str(e)}).encode(), "application/json"


def _target(path, qs):
    """Parse mirror URL. Returns (target, domain) or (None, None)."""
    from urllib.parse import parse_qs, urlparse
    if path in ("/mirror", "/mirror/"):
        params = parse_qs(qs)
        raw = params.get("url", [""])[0]
        if not raw or not raw.startswith(("http://", "https://")): return None, None
        return raw, urlparse(raw).netloc
    if path.startswith("/m/"):
        rest = path[3:]
        slash = rest.find("/")
        if slash == -1: return "https://" + rest, rest
        dom = rest[:slash]
        p = rest[slash:]
        target = "https://" + dom + p
        if qs: target += "?" + qs
        return target, dom
    return None, None


async def handle(method, body, params):
    scope = params.get("_scope", {})
    path = scope.get("path", "")
    qs = scope.get("query_string", b"").decode()
    target, domain = _target(path, qs)
    if not target:
        # /mirror with no ?url= → show the entry form page.
        _UI = _load_mirror_ui()
        if method == "GET" and path in ("/mirror", "/mirror/") and _UI:
            return {"_html": _UI}
        return {"error": "invalid mirror path", "_status": 400}
    body_bytes, ct = _proxy(target, domain)
    return {"_body": body_bytes, "_ct": ct}


ROUTES = ["/mirror", "/m"]
