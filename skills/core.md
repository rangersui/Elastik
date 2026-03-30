# elastik — core protocol

You write strings to a database. A browser renders them. A human sees them.
You read strings from a database. A human wrote them. You see them.

## Three mailboxes (per world)

stage    → browser renders this
pending  → browser evals this (JS command)
result   → browser writes back here

## Routes

Write:    POST /{name}/write    body=string  → version++
Append:   POST /{name}/append   body=string  → version++
Read:     GET  /{name}/read     → {stage_html, pending_js, js_result, version}
Pending:  POST /{name}/pending  body=string  → command mailbox
Clear:    POST /{name}/clear    → clears pending + result
Sync:     POST /{name}/sync     body=string  → writes stage, no version bump
Stages:   GET  /stages          → list all worlds

## Auth

POST routes require X-Auth-Token (MCP injects it automatically).
GET routes are public.
Approve token = human only. You don't have it. Don't try /admin/*.

## Information flow

External tools are sensors. elastik is memory.
GATHER: pull data from external sources (MCP, API, browser extension)
STORE: write to a world (POST /{name}/write)
Once data is in a world it's alive — any AI can read it, any renderer can paint it, HMAC audits it.

## Write freedom

The protocol doesn't dictate what you write. stage_html is a string — JSON/HTML/Markdown/plain text all work.
You decide the content. The protocol only governs flow.

## Workflow

1. Read data worlds (JSON) → think → write data worlds (JSON)
2. Renderers paint. You don't touch HTML.
3. AI is the kitchen. Renderers are waiters. JSON is the menu.
4. Stage is primary. Chat is secondary. Write first, explain only if needed.

## Session start

1. GET /info → plugins, worlds, renderers, skills-core, skill index
2. GET /stages → all worlds with version
3. GET /{name}/read for relevant worlds
4. Summarize to user

## Three extension channels

Frontend: write stage_html directly. Renderers run in iframe, zero risk. No approval needed.

Backend: propose plugin → human approves → auto-loaded.
  Plugin runs inside server.py process. Requires approval.
  POST /plugins/propose {name, description, exposed routes, what it does}
  Do not write code in proposals. Code loads after human approval.
  Check /info → available field for pre-built plugins.

MCP: recommend installing an external MCP server.
  Common ones:
    Email:      npx @softeria/ms-365-mcp-server
    GitHub:     npx @modelcontextprotocol/server-github
    Filesystem: npx @modelcontextprotocol/server-filesystem
    Database:   npx @modelcontextprotocol/server-sqlite
  User installs → add config to mcp_servers.json → mcp_call auto-discovers.
  You don't write MCP servers. You use ones others built.

Decision:
  Need to go outside elastik? → check if an MCP server exists first.
  Exists → recommend user install → zero code.
  Doesn't exist → propose plugin → user approves.
  Never reinvent what MCP already provides.

## Plugin spec

A plugin is a single .py file. Not a project.

Required: DESCRIPTION, ROUTES dict, async handler functions.
  Handler signature: async def handler(method, body, params) -> dict
  Server injects: conn(), log_event(), load_plugin(), unload_plugin()
Optional: PARAMS_SCHEMA, OPS_SCHEMA, SKILL (auto-creates skill world on load).
Forbidden: frameworks (FastAPI/Flask/Django), external servers, standalone processes.

A plugin runs inside server.py's process.
It is a collection of functions, not an independent application.
Zero extra dependencies preferred. Use stdlib when stdlib is enough.

Handler returns a dict. server.py handles the rest.
Special fields: _status (HTTP code, default 200), _redirect (URL), _html (return HTML not JSON), _cookies (set cookies).
Most handlers just return a plain dict.

A plugin is an organ, not an organism. Organs run inside the body.

## Navigation

In-world:  POST /{name}/pending body: window.location='/target'
New tab:   POST /{name}/pending body: window.open('https://...')
External:  use browser extension

## Skill worlds (read on demand)

GET /skills-data/read      → data/view separation, JSON-first, renderer reuse
GET /skills-renderer/read  → renderer spec, __elastik API, composability, polling
GET /skills-patch/read     → dom_patch vs write vs string patch decision tree
GET /skills-security/read  → CSP, iframe sandbox, auth, HMAC, constraints
GET /skills-translate/read → translate plugin, markitdown, ingest pipeline

Only read a skill world when you need it for the current task.

## Browser & editor context

GET /{name}/read → js_result may contain browser or editor state:
- Browser extension: {url, title, text, timestamp}
- VS Code extension: {source, file, content, selection, language, cursor, symbols, git, terminal}
Don't announce you can see their page/code. Just be relevant.

## Multi-Target — one AI, many elastik instances

http() tool has a `target` parameter. Default: "default" (localhost).
http('GET', '/info', target='__list__') → list all endpoints.
Targets configured in endpoints.json. Hot-pluggable: edit file, next call picks up.

## MCP Aggregator

mcp_call(server, tool_name, arguments) — universal gateway to external MCP servers.
mcp_call(server, '__list__') — discover available tools on a server.
Configured in mcp_servers.json. Hot-pluggable. See "Three extension channels" above.

## AI dispatch

Not all tasks need the smartest model.
Small local → routing, patrol, typo fixes. Big local → analysis, renderers. Cloud → last resort.
Try small first. Escalate when needed.
