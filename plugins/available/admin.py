"""Hot plug admin — load/unload/list plugins via HTTP.

Install: lucy install admin
Protected by auth middleware (requires X-Auth-Token).
"""

DESCRIPTION = "Hot plug admin — load/unload/list plugins at runtime"
ROUTES = {}

PARAMS_SCHEMA = {
    "/admin/load": {
        "method": "POST",
        "params": {"name": {"type": "string", "required": True, "description": "Plugin name to load"}},
        "example": {"name": "patch"},
        "returns": {"ok": "boolean", "loaded": "string"}
    },
    "/admin/unload": {
        "method": "POST",
        "params": {"name": {"type": "string", "required": True, "description": "Plugin name to unload"}},
        "example": {"name": "patch"},
        "returns": {"ok": "boolean", "unloaded": "string"}
    },
    "/admin/list": {
        "method": "GET",
        "params": {},
        "returns": {"plugins": "array"}
    },
    "/admin/status": {
        "method": "GET",
        "params": {},
        "returns": {"plugins": "int", "routes": "array"}
    },
}


async def handle_load(method, body, params):
    name = params.get("name", "")
    if not name and body:
        name = body.decode().strip() if isinstance(body, bytes) else body.strip()
    if not name:
        return {"error": "name required"}
    load_plugin(name)
    return {"ok": True, "loaded": name}


async def handle_unload(method, body, params):
    name = params.get("name", "")
    if not name and body:
        name = body.decode().strip() if isinstance(body, bytes) else body.strip()
    if not name:
        return {"error": "name required"}
    unload_plugin(name)
    return {"ok": True, "unloaded": name}


async def handle_list(method, body, params):
    return {"plugins": list(_plugin_meta)}


async def handle_status(method, body, params):
    return {"plugins": len(_plugin_meta), "routes": list(_plugins.keys())}


ROUTES["/admin/load"] = handle_load
ROUTES["/admin/unload"] = handle_unload
ROUTES["/admin/list"] = handle_list
ROUTES["/admin/status"] = handle_status
