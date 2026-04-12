# elastik plugin spec v1

A plugin is a .py file in the plugins/ directory.

## Required declarations

```python
ROUTES = ["/path"]               # routes to register
AUTH = "none" | "auth" | "approve"  # permission level
```

## Required implementation

```python
async def handle(method, body, params):
    # method: GET/POST/PUT/DELETE/PROPFIND/...
    # body:   request body string (already decoded)
    # params: query string dict + _scope
    # returns:
    #   {...}             → auto json.dumps
    #   {"_html": str}    → text/html
    #   {"_body": str, "_ct": "..."} → custom content-type
    #   {"_status": int}  → custom status code
    #   {"_redirect": str} → 302
    #   {"_headers": [[k,v], ...]} → custom response headers
    return {"ok": True}
```

## server.py guarantees

- AUTH check completes before handle is called
- Plugins do not need to import any auth functions
- Plugins do not need to check tokens
- Body size is capped (MAX_BODY)
- Paths are validated (no .. or //)

## Plugins cannot

- Modify server.py global state
- Call send/receive directly
- Check auth themselves (redundant and error-prone)
- Register core routes like /stages /read /write

## Core routes (owned by server.py, never pluginized)

```
/<world>/read
/<world>/write
/<world>/append
/<world>/pending
/<world>/result
/<world>/clear
/<world>/sync
/stages
/  → index.html
```

## Everything else is a plugin

Auth lives in the kernel, not the application. Applications checking
auth themselves will always miss cases. The kernel checking uniformly
cannot.
