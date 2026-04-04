"""Safe file system plugin — read anywhere, write to whitelisted dirs only.

Handler signature: async def handler(method, body, params) -> dict
"""

import os, json
from pathlib import Path

DESCRIPTION = "Safe file system — read anywhere, write to data/backups only"
ROUTES = {}

# _ROOT is injected by server.py (project root). Don't compute from __file__.
_CONF = _ROOT / "conf" / "fs.json"

# defaults: empty — human opens dirs in conf/fs.json as needed
_READ_DIRS = []
_WRITE_DIRS = []
_DENY_WRITE = ["*.py", "*.json", "*.env", "*.toml", "*.yaml", "*.yml", "*.sh"]

def _load_conf():
    global _READ_DIRS, _WRITE_DIRS, _DENY_WRITE
    if _CONF.exists():
        try:
            c = json.loads(_CONF.read_text())
            _READ_DIRS = [str((_ROOT / d).resolve()) for d in c.get("read_dirs", _READ_DIRS)]
            _WRITE_DIRS = [str((_ROOT / d).resolve()) for d in c.get("write_dirs", ["data", "backups"])]
            _DENY_WRITE = c.get("deny_write", _DENY_WRITE)
        except (json.JSONDecodeError, OSError):
            pass

_load_conf()

PARAMS_SCHEMA = {
    "/proxy/fs/list": {
        "method": "POST",
        "params": {"path": {"type": "string", "required": False, "description": "Directory path"}},
        "returns": {"entries": ["object"]}
    },
    "/proxy/fs/read": {
        "method": "POST",
        "params": {"path": {"type": "string", "required": True, "description": "File path to read"}},
        "returns": {"content": "string"}
    },
    "/proxy/fs/write": {
        "method": "POST",
        "params": {
            "path": {"type": "string", "required": True, "description": "File path to write"},
            "content": {"type": "string", "required": True, "description": "File content"}
        },
        "returns": {"ok": "boolean"}
    },
}


def _check_read(path):
    if not path: return None, "path required"
    if "\x00" in path: return None, "invalid path"
    resolved = Path(os.path.abspath(path)).resolve()
    if not any(resolved.is_relative_to(Path(d).resolve()) for d in _READ_DIRS):
        return None, f"path not in read dirs"
    return str(resolved), None


def _check_write(path):
    if not path: return None, "path required"
    if "\x00" in path: return None, "invalid path"
    resolved = Path(os.path.abspath(path)).resolve()
    # must be in write whitelist
    if not any(resolved.is_relative_to(Path(d).resolve()) for d in _WRITE_DIRS):
        return None, f"write not allowed here — only {_WRITE_DIRS}"
    # deny patterns (no .py, .json, etc.)
    import fnmatch
    for pat in _DENY_WRITE:
        if fnmatch.fnmatch(resolved.name, pat):
            return None, f"file type blocked: {pat}"
    return str(resolved), None


async def handle_list(method, body, params):
    path, err = _check_read(params.get("path", str(_ROOT)))
    if err: return {"error": err}
    if not os.path.isdir(path): return {"error": "not a directory"}
    entries = []
    for name in sorted(os.listdir(path)):
        full = os.path.join(path, name)
        entries.append({"name": name, "type": "dir" if os.path.isdir(full) else "file",
                        "size": os.path.getsize(full) if os.path.isfile(full) else 0})
    return {"path": path, "entries": entries}


async def handle_read(method, body, params):
    path, err = _check_read(params.get("path", ""))
    if err: return {"error": err}
    if not os.path.isfile(path): return {"error": "not a file"}
    size = os.path.getsize(path)
    if size > 1_000_000: return {"error": "file too large", "size": size}
    try:
        with open(path, "r", encoding="utf-8") as f: content = f.read()
        return {"path": path, "content": content, "size": size}
    except UnicodeDecodeError: return {"error": "binary file"}


async def handle_write(method, body, params):
    path, err = _check_write(params.get("path", ""))
    if err: return {"error": err}
    content = body.decode("utf-8") if isinstance(body, bytes) else body
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f: f.write(content)
    return {"ok": True, "path": path, "size": len(content)}


ROUTES["/proxy/fs/write"] = handle_write
ROUTES["/proxy/fs/list"] = handle_list
ROUTES["/proxy/fs/read"] = handle_read
