"""Shell — root terminal UI + /exec POST endpoint. Approve auth.

GET /shell  → shell UI from shell-ui world (or fallback)
POST /exec  → bash/powershell, 30s timeout, text/plain output.
"""
DESCRIPTION = "/shell UI + /exec POST. Approve auth."
AUTH = "approve"
import base64, platform, subprocess
import server

def _load_shell_html():
    """Load shell HTML from shell-ui world."""
    try:
        c = server.conn("shell-ui")
        r = c.execute("SELECT stage_html FROM stage_meta WHERE id=1").fetchone()
        html = r["stage_html"] or ""
        if isinstance(html, bytes): html = html.decode("utf-8", "replace")
        return html
    except Exception:
        return ""


def _basic_user(scope):
    """Extract user field from Basic Auth header (already validated by server)."""
    for k, v in scope.get("headers", []):
        if k == b"authorization":
            try: return base64.b64decode(v.decode()[6:]).decode().split(":", 1)[0]
            except (ValueError, UnicodeDecodeError): return ""
    return ""


async def handle(method, body, params):
    scope = params.get("_scope", {})
    path = scope.get("path", "")
    if method == "GET" and path == "/shell":
        SHELL_HTML = _load_shell_html()
        if not SHELL_HTML: return {"error": "shell-ui world empty", "_status": 404}
        html = SHELL_HTML.replace("__ELASTIK_USER__", _basic_user(scope))
        return {"_html": html}
    if method == "POST" and path == "/exec":
        sh = ["powershell", "-Command", body] if platform.system() == "Windows" else ["bash", "-c", body]
        try:
            r = subprocess.run(sh, capture_output=True, timeout=30, text=True)
            out = r.stdout + r.stderr
        except subprocess.TimeoutExpired:
            out = "(timeout after 30s)"
        return {"_body": out, "_ct": "text/plain"}
    return {"error": "method not allowed", "_status": 405}


ROUTES = ["/shell", "/exec"]
