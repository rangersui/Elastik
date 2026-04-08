"""Auth plugin — X-Auth-Token middleware. Mode-aware.

Mode 1 (executor):    auth token → read/write. admin/config blocked.
Mode 2 (autonomous):  approve token → admin/config unlocked.
"""
import os

DESCRIPTION = "Token-based auth middleware"
ROUTES = {}

async def auth_middleware(scope, path, method):
    # GET always open
    if method == "GET": return True
    parts = [p for p in path.split("/") if p]
    # Admin + config + postman = approve token required — checked FIRST, before any bypass
    if path.startswith("/admin/") or path == "/proxy/postman" or (len(parts) >= 1 and parts[0].startswith("config-") and method == "POST"):
        approve = os.getenv("ELASTIK_APPROVE_TOKEN", "")
        if not approve: return False  # no approve token = locked
        headers = dict(scope.get("headers", []))
        tok = headers.get(b"x-approve-token", b"").decode()
        import hmac as _hmac
        return _hmac.compare_digest(tok, approve)
    # Browser routes — no token available (sync/result/clear for non-config worlds)
    if len(parts) == 2 and parts[1] in ("sync", "result", "clear"): return True
    # Signal worlds — ephemeral WebRTC signaling, no auth needed
    if len(parts) >= 1 and parts[0].startswith("signal-"): return True
    # Auth plugin routes must be open
    if path.startswith("/auth/"): return True
    # Plugin approve has its own token check inside handler
    if path == "/plugins/approve": return True

    # Everything else — check X-Auth-Token
    token = os.getenv("ELASTIK_TOKEN", "")
    if not token: return True  # no token set = public mode
    headers = dict(scope.get("headers", []))
    tok = headers.get(b"x-auth-token", b"").decode()
    import hmac as _hmac
    return _hmac.compare_digest(tok, token)

AUTH_MIDDLEWARE = auth_middleware
