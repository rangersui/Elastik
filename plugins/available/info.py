"""info plugin — /info endpoint. System introspection."""
DESCRIPTION = "System info and plugin registry"
NEEDS = ["_plugin_meta", "_plugins"]
from pathlib import Path
import json

PLUGINS = Path("plugins")


async def handle_info(method, body, params):
    DATA = Path("data")

    # --- skills: SKILLS.md content ---
    skills = ""
    try:
        if (DATA / "skills-core").exists():
            skills = conn("skills-core").execute("SELECT stage_html FROM stage_meta WHERE id=1").fetchone()["stage_html"]
    except Exception as e: print(f"  warn: skills-core read failed: {e}")
    if not skills:
        sp = _ROOT / "SKILLS.md"
        if sp.exists(): skills = sp.read_text(encoding="utf-8")

    # --- auth ---
    auth_name = next((p["name"] for p in _plugin_meta if p["name"] == "auth" or "auth" in p.get("description","").lower()), None)

    # --- renderers & worlds from DATA ---
    renderers, worlds = [], []
    if DATA.exists():
        for d in sorted(DATA.iterdir()):
            if d.is_dir() and (d / "universe.db").exists():
                if d.name.startswith("renderer-"): renderers.append(d.name)
                elif not d.name.startswith("config-"): worlds.append(d.name)

    # --- CDN ---
    cdn_raw = ""
    try:
        if (DATA / "config-cdn").exists():
            r = conn("config-cdn").execute("SELECT stage_html FROM stage_meta WHERE id=1").fetchone()
            if r: cdn_raw = r["stage_html"]
    except Exception as e: print(f"  warn: CDN config read failed: {e}")
    cdn = [d.strip() for d in cdn_raw.splitlines() if d.strip()] if cdn_raw.strip() else ["* (all HTTPS)"]

    # --- available (unloaded) plugins ---
    available = []
    avail_dir = PLUGINS / "available"
    if avail_dir.exists():
        loaded = {m["name"] for m in _plugin_meta}
        for f in sorted(avail_dir.glob("*.py")):
            if f.stem not in loaded:
                desc = ""
                for line in f.read_text(encoding="utf-8").splitlines():
                    if line.startswith("DESCRIPTION"):
                        try: desc = line.split("=", 1)[1].strip().strip('"').strip("'")
                        except Exception: pass
                        break
                available.append({"name": f.stem, "description": desc})

    # --- skill worlds ---
    skill_worlds = [d.name for d in sorted(DATA.iterdir())
                    if d.is_dir() and d.name.startswith("skills-") and (d / "universe.db").exists()] if DATA.exists() else []

    # --- worlds with version/updated_at (same as /stages) ---
    stages = []
    if DATA.exists():
        for d in sorted(DATA.iterdir()):
            if d.is_dir() and (d / "universe.db").exists():
                try:
                    r = conn(d.name).execute("SELECT version,updated_at FROM stage_meta WHERE id=1").fetchone()
                    stages.append({"name": d.name, "version": r["version"], "updated_at": r["updated_at"]})
                except Exception:
                    stages.append({"name": d.name})

    # --- protocol: inline 10-line summary ---
    protocol = (
        "elastik is raw ASGI + SQLite. Not FastAPI/Flask/Django.\n"
        "You write strings to worlds. The browser renders them. The human sees them.\n"
        "Three mailboxes per world: stage (HTML/MD/JSON), pending (JS command), result (browser reply).\n"
        "Routes: GET /{name}/read, POST /{name}/write, POST /{name}/append, GET /stages.\n"
        "Plugins are single .py files loaded into the server process. Not frameworks.\n"
        "Auth: POST routes need X-Auth-Token (MCP injects it). GET routes are public.\n"
        "Renderers live in iframes. They poll worlds. You write data, renderers paint.\n"
        "Never write HTML to stage unless explicitly asked. Write JSON/MD, let renderers handle display.\n"
        "Check /info 'available' field before proposing new plugins. Pre-built ones exist.\n"
        "Read SKILLS.md (in 'skills' field below) for full protocol. Read skill worlds on demand."
    )

    # --- plugin_example: first 1500 chars of a real plugin ---
    plugin_example = ""
    try:
        if avail_dir.exists():
            # prefer example.py, fall back to first available
            example_file = avail_dir / "example.py"
            if not example_file.exists():
                candidates = sorted(avail_dir.glob("*.py"))
                example_file = candidates[0] if candidates else None
            if example_file and example_file.exists():
                plugin_example = example_file.read_text(encoding="utf-8")[:1500]
    except Exception as e:
        print(f"  warn: plugin_example read failed: {e}")

    return {
        "protocol": protocol,
        "routes": list(_plugins.keys()),
        "auth": auth_name,
        "plugins": _plugin_meta,
        "available": available,
        "renderers": renderers,
        "worlds": stages,
        "skill_worlds": skill_worlds,
        "cdn": cdn,
        "skills": skills,
        "plugin_example": plugin_example,
    }


ROUTES = {"/info": handle_info}
