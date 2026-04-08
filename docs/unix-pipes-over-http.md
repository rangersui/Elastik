# Unix Pipes over HTTP

elastik routes are Unix commands. Promise chains are pipes.

```
grep error /var/log/*  |  tail -5  |  tee output.txt
```

becomes:

```js
fetch('/grep?q=error')
  .then(r => r.json())
  .then(ws => fetch('/tail?world=' + ws[0] + '&n=5'))
  .then(r => r.text())
  .then(t => __elastik.sync(t))
```

Same structure. Different transport.

## The mapping

| Unix | HTTP | What it does |
|------|------|-------------|
| `grep pattern *` | `GET /grep?q=pattern` | Search all worlds, return matching names |
| `tail -n 5 file` | `GET /tail?world=x&n=5` | Last n lines of a world |
| `head -n 5 file` | `GET /head?world=x&n=5` | First n lines of a world |
| `wc file` | `GET /wc?world=x` | Line/word/byte count |
| `echo hello` | `POST /echo` body=hello | Return body unchanged |
| `/dev/null` | `POST /null` | Swallow input, 204 No Content |
| `uptime` | `GET /health` | ok + uptime seconds |
| `du -sh *` | `GET /db/size` | Storage per world |

## Why this works

Promise `.then()` is `|`. Each fetch output feeds the next input.

```
stdin  →  process  →  stdout
  ↕          ↕          ↕
request →  route   →  response
```

Array methods are pipes too:

```js
data
  .filter(x => x.active)   // grep
  .map(x => x.name)         // awk '{print $1}'
  .sort()                    // sort
  .join('\n')                // paste
```

## AI writes shell scripts

The three-mailbox loop already exists:

1. AI writes a fetch chain to `pending` (JS command)
2. Browser evals it
3. Result goes to `result`
4. AI reads `result`

So when a user says "find all worlds with WebRTC, show last 10 lines":

```js
// AI generates this, writes to pending:
fetch('/grep?q=WebRTC')
  .then(r => r.json())
  .then(ws => Promise.all(
    ws.map(w => fetch('/tail?world=' + w + '&n=10').then(r => r.text()))
  ))
  .then(results => __elastik.result(results.join('\n---\n')))
```

Browser runs it. AI reads the result. No server-side orchestration.

## Distributed by default

fetch() takes a URL. Change the host, search a remote node:

```js
// Search local
fetch('/grep?q=error')

// Search remote
fetch('http://10.0.0.5:3005/grep?q=error')

// Search both, merge
Promise.all([
  fetch('/grep?q=error').then(r => r.json()),
  fetch('http://10.0.0.5:3005/grep?q=error').then(r => r.json())
]).then(([local, remote]) => [...local, ...remote])
```

No service mesh. No message bus. Just HTTP.

## HTTP is the bus

Traditional OS has multiple buses: memory, PCIe, USB, SATA. Different protocols, different speeds, different drivers.

elastik has one bus: HTTP.

```
browser  → daemon    HTTP
plugin   → daemon    stdin/stdout (local HTTP equivalent)
daemon   → daemon    HTTP
AI       → daemon    HTTP (MCP)
phone    → daemon    HTTP
```

One protocol. No drivers. A Raspberry Pi and a Mac Studio speak the same bus. A browser tab and a Python plugin speak the same bus. There is nothing to configure because there is only one thing.

stdin/stdout is the local degenerate case of HTTP — same semantics (request in, response out), zero network overhead. That's why CGI plugins work: they're HTTP over file descriptors.

## Install

Not loaded by default. Load it:

```bash
# Python
curl -X POST localhost:3005/admin/load -H "X-Approve-Token: $TOKEN" -d devtools

# Go Lite (auto-detected at startup if in plugins/ or plugins/available/)
curl -X POST localhost:3005/plugins/reload -H "X-Auth-Token: $TOKEN"
```

Source: `plugins/available/devtools.py` — one file, both runtimes.
