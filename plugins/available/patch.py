"""Patch — composable string operations on any world's stage.

POST /proxy/patch  body: {"world": "default", "ops": [...]}

Supported ops:
  insert       {op:"insert", pos:0, text:"hello"}
  delete       {op:"delete", start:0, end:5}
  replace      {op:"replace", find:"old", text:"new", count:1}
  replace_all  {op:"replace_all", find:"old", text:"new"}
  slice        {op:"slice", start:0, end:100}
  prepend      {op:"prepend", text:"header"}
  regex_replace {op:"regex_replace", pattern:"\\d+", text:"X", count:0}

Install: lucy install patch
"""
import json, re

DESCRIPTION = "String operations: insert, delete, replace, prepend, slice, regex"
ROUTES = {}


def apply_patch(html, ops):
    count = 0
    for op in ops:
        t = op.get("op")
        if t == "insert":
            pos = max(0, min(op.get("pos", 0), len(html)))
            html = html[:pos] + op.get("text", "") + html[pos:]; count += 1
        elif t == "delete":
            s, e = max(0, op.get("start", 0)), min(len(html), op.get("end", 0))
            html = html[:s] + html[e:]; count += 1
        elif t == "replace":
            f, txt, n = op.get("find", ""), op.get("text", ""), op.get("count", 1)
            if f: html = html.replace(f, txt, n); count += 1
        elif t == "replace_all":
            f, txt = op.get("find", ""), op.get("text", "")
            if f: html = html.replace(f, txt); count += 1
        elif t == "slice":
            html = html[op.get("start", 0):op.get("end", len(html))]; count += 1
        elif t == "prepend":
            html = op.get("text", "") + html; count += 1
        elif t == "regex_replace":
            p, txt, n = op.get("pattern", ""), op.get("text", ""), op.get("count", 0)
            if p: html = re.sub(p, txt, html, count=n); count += 1
    return html, count


async def handle_patch(method, body, params):
    data = body if isinstance(body, dict) else json.loads(body if isinstance(body, str) else body.decode("utf-8"))
    world = data.get("world", "default")
    ops = data.get("ops", [])
    if not ops:
        return {"error": "no ops provided"}
    c = conn(world)
    old = c.execute("SELECT stage_html FROM stage_meta WHERE id=1").fetchone()["stage_html"]
    new_html, applied = apply_patch(old, ops)
    c.execute("UPDATE stage_meta SET stage_html=?,version=version+1,updated_at=datetime('now') WHERE id=1", (new_html,))
    c.commit()
    log_event(world, "stage_patched", {"ops": len(ops), "applied": applied})
    v = c.execute("SELECT version FROM stage_meta WHERE id=1").fetchone()["version"]
    return {"version": v, "applied": applied, "length": len(new_html)}


ROUTES["/proxy/patch"] = handle_patch
