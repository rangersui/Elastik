"""sse.py — Server-sent events. Push on write, no client polling.

GET /stream/{name} → text/event-stream
Emits `event: update\\ndata: {...}` whenever the world's version changes.

No polling on the wire. Browser opens an EventSource, waits, receives
events only when the world actually changes. Shannon-optimal: zero
bytes when idle, full payload only on real change.

Install:
    curl -X POST "http://localhost:3005/admin/load?name=sse" \\
        -H "Authorization: Bearer $APPROVE"

Browser:
    const es = new EventSource('/stream/foo');
    es.addEventListener('update', (e) => {
        const d = JSON.parse(e.data);
        document.body.innerHTML = d.stage_html;
    });

Terminal test:
    curl -N "http://localhost:3005/stream/foo" -H "Authorization: Bearer $TOKEN"
    # then in another terminal:
    curl -X POST "http://localhost:3005/foo/write" -H "Authorization: Bearer $TOKEN" -d "hello"
    # → first terminal receives event immediately
"""
import asyncio, json
import server

DESCRIPTION = "Server-sent events — push per-world updates on version change"
ROUTES = ["/stream"]   # prefix match: /stream/foo, /stream/a/b
AUTH = "auth"          # same level as /read — token required

PARAMS_SCHEMA = {
    "/stream/{name}": {
        "method": "GET",
        "description": "Open SSE stream for world. Emits 'update' events on version bump. Keeps connection open.",
        "returns": "text/event-stream",
    },
}

_POLL = 0.1       # internal DB poll interval (seconds)
_HB_EVERY = 30    # heartbeat every N polls (3s at 100ms)


async def handle(method, body, params):
    send = params.get("_send")
    scope = params.get("_scope", {})
    if not send:
        return {"error": "server does not expose raw send; SSE unavailable", "_status": 500}
    if method != "GET":
        return {"error": "SSE is GET only", "_status": 405}

    # /stream/foo → name = "foo" ; /stream/a/b → name = "a/b"
    path = scope.get("path", "").rstrip("/")
    if not path.startswith("/stream/") or path == "/stream":
        return {"error": "path must be /stream/{name}", "_status": 400}
    name = path[len("/stream/"):]
    if not server._valid_name(name):
        return {"error": "invalid world name", "_status": 400}
    if not (server.DATA / server._disk_name(name) / "universe.db").exists():
        return {"error": "world not found", "_status": 404}

    c = conn(name)

    # Start SSE response — headers only. Body chunks follow.
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [
            [b"content-type", b"text/event-stream; charset=utf-8"],
            [b"cache-control", b"no-cache"],
            [b"connection", b"keep-alive"],
            [b"x-accel-buffering", b"no"],  # disable proxy buffering
        ],
    })

    def _snapshot():
        r = c.execute("SELECT stage_html,version,ext FROM stage_meta WHERE id=1").fetchone()
        raw = r["stage_html"] or ""
        if isinstance(raw, bytes):
            try: raw = raw.decode("utf-8")
            except UnicodeDecodeError: raw = ""
        ext = r["ext"] or "html"
        return r["version"], json.dumps({
            "version": r["version"], "stage_html": raw,
            "ext": ext, "type": ext,
        }, ensure_ascii=False)

    last_v = -1
    ticks = 0
    try:
        while True:
            v, data = _snapshot()
            if v != last_v:
                msg = f"event: update\ndata: {data}\n\n".encode("utf-8")
                await send({"type": "http.response.body", "body": msg, "more_body": True})
                last_v = v
                ticks = 0
            else:
                ticks += 1
                if ticks >= _HB_EVERY:
                    # Comment line = heartbeat. EventSource ignores it silently,
                    # but it keeps proxies/NATs from closing the connection.
                    await send({"type": "http.response.body", "body": b": hb\n\n", "more_body": True})
                    ticks = 0
            await asyncio.sleep(_POLL)
    except asyncio.CancelledError:
        raise
    except Exception:
        # Client disconnect or send failure — exit loop cleanly
        pass
    finally:
        try: await send({"type": "http.response.body", "body": b"", "more_body": False})
        except Exception: pass

    return None  # signal: plugin streamed its own response, dispatcher should skip auto-reply
