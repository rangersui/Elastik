"""Shell — root terminal UI + /exec POST endpoint. Approve auth.

GET /shell  → shell.html (user substituted from Basic Auth user field)
POST /exec  → bash/powershell, 30s timeout, text/plain output.
"""
DESCRIPTION = "/shell UI + /exec POST. Approve auth."
AUTH = "approve"
import base64, platform, subprocess
from pathlib import Path
import server

_SHELL = Path(server.__file__).resolve().parent / "shell.html"
SHELL_HTML = _SHELL.read_text(encoding="utf-8") if _SHELL.exists() else ""


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
        if not SHELL_HTML: return {"error": "shell.html missing", "_status": 404}
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
