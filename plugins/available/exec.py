"""Shell plugin — execute commands.

Install: lucy install exec
Handler signature: async def handler(method, body, params) -> dict
"""

import os, subprocess
from pathlib import Path

_in_container = os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")
DESCRIPTION = "Execute shell commands" + (" (container)" if _in_container else " (WARNING: no container isolation)")
ROUTES = {}

if not _in_container:
    print("  ⚠ exec plugin loaded WITHOUT container isolation. Commands run on host.")


async def handle_exec(method, body, params):
    cmd = body.decode("utf-8") if isinstance(body, bytes) else body
    if not cmd: return {"error": "no command"}
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=str(_ROOT))
        return {"stdout": r.stdout, "stderr": r.stderr, "code": r.returncode, "container": _in_container}
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "timeout": 30, "container": _in_container}


ROUTES["/proxy/exec"] = handle_exec
