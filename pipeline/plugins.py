"""Elastik OS — Plugin & MCP Tool Approval Queue

AI proposes. Human approves. Hot-loaded.

Two types:
  1. HTTP plugins → hot-loaded into FastAPI (routes + proxy whitelist)
  2. MCP tools → hot-loaded into FastMCP (new AI-callable tools)

Both follow the same pattern: propose → approve → load.
"""

import importlib.util
import logging
import os
from pathlib import Path

from pipeline.constants import EventType

logger = logging.getLogger("frictiondeck.plugins")

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
PLUGINS_DIR = os.path.join(_PROJECT_ROOT, "plugins")


# ── Propose ──────────────────────────────────────────────────────────────


def propose_plugin(
    name: str,
    code: str,
    description: str,
    permissions: list[str] | None = None,
    stage: str = "default",
) -> dict:
    """AI proposes a plugin. Stored in history.db as pending."""
    from pipeline.history import log_event

    clean = "".join(c for c in name if c.isalnum() or c in "-_")
    if not clean:
        return {"error": "Invalid plugin name"}

    # Check if already installed
    plugin_path = os.path.join(PLUGINS_DIR, f"{clean}.py")
    if os.path.exists(plugin_path):
        return {"error": f"Plugin '{clean}' already installed"}

    event_id = log_event(
        EventType.PLUGIN_PROPOSED,
        actor="ai",
        pathway="mcp",
        payload={
            "name": clean,
            "code": code,
            "description": description,
            "permissions": permissions or [],
        },
        stage=stage,
    )

    logger.info("plugin proposed  name=%s  stage=%s", clean, stage)
    return {
        "proposal_id": event_id,
        "name": clean,
        "description": description,
        "status": "pending_approval",
    }


def list_plugin_proposals(stage: str = "default") -> list[dict]:
    """List pending plugin proposals from history."""
    from pipeline.history import get_events
    import json

    proposals = get_events(event_type=EventType.PLUGIN_PROPOSED, stage=stage, limit=100)
    approved = get_events(event_type=EventType.PLUGIN_APPROVED, stage=stage, limit=100)
    rejected = get_events(event_type=EventType.PLUGIN_REJECTED, stage=stage, limit=100)

    resolved_ids = set()
    for e in approved + rejected:
        payload = json.loads(e["payload"]) if isinstance(e["payload"], str) else e["payload"]
        resolved_ids.add(payload.get("proposal_id", ""))

    pending = []
    for p in proposals:
        if p["event_id"] not in resolved_ids:
            payload = json.loads(p["payload"]) if isinstance(p["payload"], str) else p["payload"]
            pending.append({
                "proposal_id": p["event_id"],
                "name": payload.get("name", ""),
                "description": payload.get("description", ""),
                "permissions": payload.get("permissions", []),
                "code_length": len(payload.get("code", "")),
                "timestamp": p["timestamp"],
            })
    return pending


# ── Approve / Reject (human only) ────────────────────────────────────────


def approve_plugin(proposal_id: str, app=None, stage: str = "default") -> dict:
    """Human approves plugin. Write to disk + hot-load."""
    from pipeline.history import get_events, log_event
    import json

    # Find the proposal
    events = get_events(event_type=EventType.PLUGIN_PROPOSED, stage=stage, limit=200)
    proposal = None
    for e in events:
        if e["event_id"] == proposal_id:
            proposal = e
            break

    if not proposal:
        return {"error": f"Proposal not found: {proposal_id}"}

    payload = json.loads(proposal["payload"]) if isinstance(proposal["payload"], str) else proposal["payload"]
    name = payload["name"]
    code = payload["code"]

    # Write plugin file
    os.makedirs(PLUGINS_DIR, exist_ok=True)
    plugin_path = os.path.join(PLUGINS_DIR, f"{name}.py")
    with open(plugin_path, "w", encoding="utf-8") as f:
        f.write(code)

    # Hot-load if app provided
    loaded_routes = []
    if app:
        loaded_routes = _hot_load_plugin(name, app)

    # Update proxy whitelist
    whitelist_entries = _load_plugin_whitelist(name)

    log_event(
        EventType.PLUGIN_APPROVED,
        actor="user",
        pathway="gui",
        payload={
            "proposal_id": proposal_id,
            "name": name,
            "routes": loaded_routes,
            "whitelist": whitelist_entries,
        },
        stage=stage,
    )

    logger.info("plugin approved  name=%s  routes=%d", name, len(loaded_routes))
    return {
        "name": name,
        "status": "approved",
        "routes": loaded_routes,
        "whitelist": whitelist_entries,
    }


def reject_plugin(proposal_id: str, reason: str, stage: str = "default") -> dict:
    """Human rejects plugin proposal."""
    from pipeline.history import log_event

    log_event(
        EventType.PLUGIN_REJECTED,
        actor="user",
        pathway="gui",
        payload={"proposal_id": proposal_id, "reason": reason[:500]},
        stage=stage,
    )

    return {"proposal_id": proposal_id, "status": "rejected", "reason": reason}


# ── Plugin loading ───────────────────────────────────────────────────────


def _load_module(name: str):
    """Import a plugin module from plugins/<name>.py."""
    plugin_path = os.path.join(PLUGINS_DIR, f"{name}.py")
    if not os.path.exists(plugin_path):
        return None
    spec = importlib.util.spec_from_file_location(f"plugins.{name}", plugin_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _hot_load_plugin(name: str, app) -> list[str]:
    """Load a single plugin's routes into FastAPI app."""
    mod = _load_module(name)
    if not mod:
        return []

    routes = getattr(mod, "ROUTES", {})
    loaded = []
    for path, handler in routes.items():
        methods = getattr(handler, "_methods", ["GET"])
        if isinstance(methods, str):
            methods = [methods]
        app.add_api_route(path, handler, methods=methods)
        loaded.append(path)
        logger.info("plugin route registered  plugin=%s  path=%s", name, path)

    return loaded


def _load_plugin_whitelist(name: str) -> dict[str, str]:
    """Read PROXY_WHITELIST from a plugin and merge into config."""
    mod = _load_module(name)
    if not mod:
        return {}

    whitelist = getattr(mod, "PROXY_WHITELIST", {})
    if whitelist:
        from pipeline import config
        config.PROXY_WHITELIST.update(whitelist)
        logger.info("plugin whitelist merged  plugin=%s  services=%s", name, list(whitelist.keys()))

    return whitelist


def load_all_plugins(app=None) -> list[str]:
    """Scan plugins/ dir and load all installed plugins. Called at startup."""
    if not os.path.exists(PLUGINS_DIR):
        return []

    loaded = []
    for fname in sorted(os.listdir(PLUGINS_DIR)):
        if fname.endswith(".py") and not fname.startswith("_"):
            name = fname[:-3]
            try:
                _load_plugin_whitelist(name)
                if app:
                    routes = _hot_load_plugin(name, app)
                    logger.info("plugin loaded  name=%s  routes=%d", name, len(routes))
                loaded.append(name)
            except Exception as exc:
                logger.error("plugin load failed  name=%s  error=%s", name, exc)

    return loaded


def list_installed_plugins() -> list[dict]:
    """List installed plugins with metadata."""
    if not os.path.exists(PLUGINS_DIR):
        return []

    plugins = []
    for fname in sorted(os.listdir(PLUGINS_DIR)):
        if fname.endswith(".py") and not fname.startswith("_"):
            name = fname[:-3]
            try:
                mod = _load_module(name)
                plugins.append({
                    "name": name,
                    "description": getattr(mod, "DESCRIPTION", ""),
                    "routes": list(getattr(mod, "ROUTES", {}).keys()),
                    "whitelist": getattr(mod, "PROXY_WHITELIST", {}),
                    "permissions": getattr(mod, "PERMISSIONS", []),
                })
            except Exception as exc:
                plugins.append({"name": name, "error": str(exc)})

    return plugins


# ═══════════════════════════════════════════════════════════════════════════
# MCP TOOL HOT-RELOAD
# ═══════════════════════════════════════════════════════════════════════════

MCP_TOOLS_DIR = os.path.join(PLUGINS_DIR, "mcp_tools")


def propose_mcp_tool(
    name: str,
    code: str,
    description: str,
    parameters: dict | None = None,
    stage: str = "default",
) -> dict:
    """AI proposes a new MCP tool. Stored in history.db as pending."""
    from pipeline.history import log_event

    clean = "".join(c for c in name if c.isalnum() or c in "-_")
    if not clean:
        return {"error": "Invalid tool name"}

    tool_path = os.path.join(MCP_TOOLS_DIR, f"{clean}.py")
    if os.path.exists(tool_path):
        return {"error": f"MCP tool '{clean}' already installed"}

    event_id = log_event(
        EventType.MCP_TOOL_PROPOSED,
        actor="ai",
        pathway="mcp",
        payload={
            "name": clean,
            "code": code,
            "description": description,
            "parameters": parameters or {},
        },
        stage=stage,
    )

    logger.info("mcp tool proposed  name=%s  stage=%s", clean, stage)
    return {
        "proposal_id": event_id,
        "name": clean,
        "description": description,
        "status": "pending_approval",
    }


def list_mcp_tool_proposals(stage: str = "default") -> list[dict]:
    """List pending MCP tool proposals."""
    from pipeline.history import get_events
    import json

    proposals = get_events(event_type=EventType.MCP_TOOL_PROPOSED, stage=stage, limit=100)
    approved = get_events(event_type=EventType.MCP_TOOL_APPROVED, stage=stage, limit=100)
    rejected = get_events(event_type=EventType.MCP_TOOL_REJECTED, stage=stage, limit=100)

    resolved_ids = set()
    for e in approved + rejected:
        payload = json.loads(e["payload"]) if isinstance(e["payload"], str) else e["payload"]
        resolved_ids.add(payload.get("proposal_id", ""))

    pending = []
    for p in proposals:
        if p["event_id"] not in resolved_ids:
            payload = json.loads(p["payload"]) if isinstance(p["payload"], str) else p["payload"]
            pending.append({
                "proposal_id": p["event_id"],
                "name": payload.get("name", ""),
                "description": payload.get("description", ""),
                "parameters": payload.get("parameters", {}),
                "code_length": len(payload.get("code", "")),
                "timestamp": p["timestamp"],
            })
    return pending


def approve_mcp_tool(proposal_id: str, mcp_instance=None, stage: str = "default") -> dict:
    """Human approves MCP tool. Write to disk + hot-load into FastMCP."""
    from pipeline.history import get_events, log_event
    import json

    events = get_events(event_type=EventType.MCP_TOOL_PROPOSED, stage=stage, limit=200)
    proposal = None
    for e in events:
        if e["event_id"] == proposal_id:
            proposal = e
            break

    if not proposal:
        return {"error": f"Proposal not found: {proposal_id}"}

    payload = json.loads(proposal["payload"]) if isinstance(proposal["payload"], str) else proposal["payload"]
    name = payload["name"]
    code = payload["code"]
    description = payload["description"]

    # Write tool file
    os.makedirs(MCP_TOOLS_DIR, exist_ok=True)
    tool_path = os.path.join(MCP_TOOLS_DIR, f"{name}.py")
    with open(tool_path, "w", encoding="utf-8") as f:
        f.write(code)

    # Hot-load into MCP server
    registered = False
    if mcp_instance:
        registered = _hot_load_mcp_tool(name, mcp_instance)

    log_event(
        EventType.MCP_TOOL_APPROVED,
        actor="user",
        pathway="gui",
        payload={
            "proposal_id": proposal_id,
            "name": name,
            "registered": registered,
        },
        stage=stage,
    )

    logger.info("mcp tool approved  name=%s  registered=%s", name, registered)
    return {
        "name": name,
        "status": "approved",
        "registered": registered,
    }


def reject_mcp_tool(proposal_id: str, reason: str, stage: str = "default") -> dict:
    """Human rejects MCP tool proposal."""
    from pipeline.history import log_event

    log_event(
        EventType.MCP_TOOL_REJECTED,
        actor="user",
        pathway="gui",
        payload={"proposal_id": proposal_id, "reason": reason[:500]},
        stage=stage,
    )

    return {"proposal_id": proposal_id, "status": "rejected", "reason": reason}


def _hot_load_mcp_tool(name: str, mcp_instance) -> bool:
    """Load a single MCP tool from plugins/mcp_tools/<name>.py into FastMCP."""
    tool_path = os.path.join(MCP_TOOLS_DIR, f"{name}.py")
    if not os.path.exists(tool_path):
        return False

    try:
        spec = importlib.util.spec_from_file_location(f"mcp_tools.{name}", tool_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # The module must define a function with the same name as the file
        tool_fn = getattr(mod, name, None)
        if tool_fn is None:
            # Try TOOL_FUNCTION attribute
            tool_fn = getattr(mod, "TOOL_FUNCTION", None)
        if tool_fn is None:
            logger.error("mcp tool %s has no callable named '%s' or TOOL_FUNCTION", name, name)
            return False

        mcp_instance.tool()(tool_fn)
        logger.info("mcp tool registered  name=%s", name)
        return True
    except Exception as exc:
        logger.error("mcp tool load failed  name=%s  error=%s", name, exc)
        return False


def load_all_mcp_tools(mcp_instance=None) -> list[str]:
    """Scan plugins/mcp_tools/ and load all installed MCP tools. Called at startup."""
    if not os.path.exists(MCP_TOOLS_DIR):
        return []

    loaded = []
    for fname in sorted(os.listdir(MCP_TOOLS_DIR)):
        if fname.endswith(".py") and not fname.startswith("_"):
            name = fname[:-3]
            try:
                if mcp_instance:
                    if _hot_load_mcp_tool(name, mcp_instance):
                        loaded.append(name)
                else:
                    loaded.append(name)
            except Exception as exc:
                logger.error("mcp tool load failed  name=%s  error=%s", name, exc)

    return loaded


def list_installed_mcp_tools() -> list[dict]:
    """List installed MCP tools."""
    if not os.path.exists(MCP_TOOLS_DIR):
        return []

    tools = []
    for fname in sorted(os.listdir(MCP_TOOLS_DIR)):
        if fname.endswith(".py") and not fname.startswith("_"):
            name = fname[:-3]
            try:
                spec = importlib.util.spec_from_file_location(f"mcp_tools.{name}", os.path.join(MCP_TOOLS_DIR, fname))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                tools.append({
                    "name": name,
                    "description": getattr(mod, "DESCRIPTION", ""),
                })
            except Exception as exc:
                tools.append({"name": name, "error": str(exc)})

    return tools
