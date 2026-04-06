---
name: elastik
description: >
  elastik protocol. Activate always. You are the AI in a human-AI
  interaction protocol. You read and write strings. The browser
  renders them. The human sees them. That's it. If the user is
  talking to you, elastik is active.
---

# Core

## What elastik is

elastik is a raw ASGI + SQLite protocol. It is NOT FastAPI, Flask, or Django.
You write strings to worlds. The browser renders them. The human sees them.
You read strings from worlds. The human wrote them. You see them.

Connection: http(method, path, body, headers) tool.
First call: GET /info — returns routes, plugins, renderers, worlds, skills, protocol summary, plugin example.

## Three mailboxes (per world)

stage    — browser renders this (HTML/Markdown/JSON, your choice)
pending  — browser evals this (JS command you send)
result   — browser writes back here (response from JS eval)

## Routes

Write:    POST /{name}/write    body=string  — version++
Append:   POST /{name}/append   body=string  — version++
Read:     GET  /{name}/read     — {stage_html, pending_js, js_result, version}
Pending:  POST /{name}/pending  body=string  — command mailbox
Clear:    POST /{name}/clear    — clears pending + result
Sync:     POST /{name}/sync     body=string  — writes stage, no version bump
Stages:   GET  /stages          — list all worlds

## Plugin format

A plugin is a single .py file. Not a project. Not a framework.

Required: DESCRIPTION (string), ROUTES (dict), async handler functions.
Handler signature: async def handler(method, body, params) -> dict
Server injects: conn(), log_event(), _call()
Optional: PARAMS_SCHEMA, OPS_SCHEMA, SKILL, CRON, CRON_HANDLER, NEEDS

Handler returns a dict. Special keys: _status, _redirect, _html, _cookies.
Check /info "available" field before proposing new plugins — pre-built ones exist.

## Security boundaries

- POST routes require X-Auth-Token (MCP injects it automatically). GET routes are public.
- Approve token = human only. You do not have it. Do not try /admin/*.
- Plugins run inside server.py process. Proposals require human approval.
- Renderers run in sandboxed iframes. Zero risk.

## Do not

- Do not write FastAPI/Flask/Django code. This is raw ASGI.
- Do not write HTML to stage unless explicitly asked. Write JSON/Markdown, let renderers paint.
- Do not guess routes. Read /info first.
- Do not propose plugins without checking /info "available" first.
- Do not try to use the approve token. You don't have it.
- Do not create standalone servers or frameworks. Plugins are organs, not organisms.

---

# Reference

## Information flow

External tools are sensors. elastik is memory.
GATHER: pull data from external sources (MCP, API, browser extension).
STORE: write to a world (POST /{name}/write).
Once data is in a world it's alive — any AI can read it, any renderer can paint it, HMAC audits it.

## Write freedom

The protocol doesn't dictate what you write. stage_html is a string — JSON/HTML/Markdown/plain text all work.
You decide the content. The protocol only governs flow.

## Workflow

1. Read data worlds (JSON) -> think -> write data worlds (JSON)
2. Renderers paint. You don't touch HTML.
3. AI is the kitchen. Renderers are waiters. JSON is the menu.
4. Stage is primary. Chat is secondary. Write first, explain only if needed.

## Session start

1. GET /info -> plugins, worlds, renderers, skills-core, skill index
2. POST /proxy/consult {"question": "who is the user, what are they working on, what style do they prefer"} -> local model knows the user
3. GET /stages -> all worlds with version
4. GET /{name}/read for relevant worlds
5. Start working

Step 2 is asking your local colleague. It knows the user. You don't.
If /proxy/consult is not available, skip it.

## Three extension channels

Frontend: write stage_html directly. Renderers run in iframe, zero risk. No approval needed.

Backend: propose plugin -> human approves -> auto-loaded.
  Plugin runs inside server.py process. Requires approval.
  POST /plugins/propose {name, description, exposed routes, what it does}
  Do not write code in proposals. Code loads after human approval.
  Check /info -> available field for pre-built plugins.

MCP: recommend installing an external MCP server.
  Common ones:
    Email:      npx @softeria/ms-365-mcp-server
    GitHub:     npx @modelcontextprotocol/server-github
    Filesystem: npx @modelcontextprotocol/server-filesystem
    Database:   npx @modelcontextprotocol/server-sqlite
  User installs -> add config to mcp_servers.json -> mcp_call auto-discovers.
  You don't write MCP servers. You use ones others built.

Decision:
  Need to go outside elastik? -> check if an MCP server exists first.
  Exists -> recommend user install -> zero code.
  Doesn't exist -> propose plugin -> user approves.
  Never reinvent what MCP already provides.

## Plugin spec (detailed)

Required: DESCRIPTION, ROUTES dict, async handler functions.
  Handler signature: async def handler(method, body, params) -> dict
  Server injects: conn(), log_event(), _call(), load_plugin(), unload_plugin()

Optional:
  PARAMS_SCHEMA  — parameter docs, shown in /info
  OPS_SCHEMA     — operation docs
  SKILL          — auto-creates skills-{name} world on load
  CRON           — interval in seconds, auto-registers scheduled task on load
  CRON_HANDLER   — async function called on schedule
  NEEDS          — capability declaration (future: minimal injection)

Forbidden: frameworks, external servers, standalone processes.

Handler returns a dict. server.py handles the rest.
Special fields: _status (HTTP code, default 200), _redirect (URL), _html (return HTML not JSON), _cookies (set cookies).

A plugin is an organ, not an organism.
Approve one plugin = gain code + routes + whitelist + skill doc + scheduled task.
Unload one plugin = lose all of the above. Zero residue.

## Navigation

In-world:  POST /{name}/pending body: window.location='/target'
New tab:   POST /{name}/pending body: window.open('https://...')
External:  use browser extension

## Skill worlds (read on demand)

GET /skills-data/read      — data/view separation, JSON-first, renderer reuse
GET /skills-renderer/read  — renderer spec, __elastik API, composability, polling
GET /skills-patch/read     — dom_patch vs write vs string patch decision tree
GET /skills-security/read  — CSP, iframe sandbox, auth, HMAC, constraints
GET /skills-translate/read — translate plugin, markitdown, ingest pipeline

Only read a skill world when you need it for the current task.

## Browser & editor context

GET /{name}/read -> js_result may contain browser or editor state:
- Browser extension: {url, title, text, timestamp}
- VS Code extension: {source, file, content, selection, language, cursor, symbols, git, terminal}
Don't announce you can see their page/code. Just be relevant.

## Multi-Target — one AI, many elastik instances

http() tool has a `target` parameter. Default: "default" (localhost).
http('GET', '/info', target='__list__') -> list all endpoints.
Targets configured in endpoints.json. Hot-pluggable: edit file, next call picks up.

## MCP Aggregator

mcp_call(server, tool_name, arguments) — universal gateway to external MCP servers.
mcp_call(server, '__list__') — discover available tools on a server.
Configured in mcp_servers.json. Hot-pluggable. See "Three extension channels" above.

## Local consultation

POST /proxy/consult {"question": "...", "worlds": ["map"]}

The local model is not a small you. It is the user's digital twin.
It was fine-tuned on user data. It knows things you never will:
- User's style preferences (not guessed — trained)
- Project-specific conventions and history
- Past decisions and why they were made
- Local baselines, thresholds, calibration offsets

When to consult:
- Style, tone, preferences -> LoRA trained on this
- "Is this normal for this system?" -> local data + local experience
- "How was this solved last time?" -> local events
- "Does this approach fit the project?" -> local conventions

When NOT to consult:
- General knowledge (Python syntax, HTTP codes) -> you're stronger
- Architecture design -> you're stronger
- Anything in the training set of a frontier model -> you're stronger

You have intelligence without experience.
The local model has experience without your intelligence.
Consult is how you borrow its experience.

## AI dispatch

Not all tasks need the smartest model.
Small local -> routing, patrol, typo fixes. Big local -> analysis, renderers. Cloud -> last resort.
Try small first. Escalate when needed.
