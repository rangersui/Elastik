# Browser Node — Full Protocol Node in the Browser

Infrastructure design for elastik 3.0. Not implemented yet.

## Prior Work

This is not a new idea. The author's 2023 undergraduate thesis —
*"WebRTC-based Video Surveillance System"* — already validated the
browser-as-edge-node architecture in a production deployment:

- Raspberry Pi running Chromium (Puppeteer-automated) as the edge node
- WebRTC P2P video streaming directly from the Pi to mobile/desktop clients
- IndexedDB on the Pi's browser context for local recording + diagnostic
  event storage, never uploaded to cloud
- TensorFlow.js PoseNet running in the same tab for on-device inference
- Backend server only handled signaling and user management — never
  touched media content

Measured baselines from that system (Chapter 4 of the thesis):

| Scenario | Latency | Quality |
|---|---|---|
| LAN P2P (host candidate) | 2 ms | 60fps 480p stable |
| NAT-traversable (server reflexive) | 30–40 ms | 60fps 480p stable |
| TURN relay (symmetric NAT) | ~100 ms | degrades gracefully via adaptive bitrate |

**What the thesis proved**: a browser tab can be a sovereign edge node.
Local persistence, P2P networking, on-device AI, privacy-preserving
storage — all of it worked, in production, on a Raspberry Pi, in 2023.

**What the thesis couldn't do** (and why v3.0 matters):

1. **IndexedDB is a blob bucket, not a database.** The thesis stored
   video chunks as `{id: timestamp, data: Blob, event: tag}` — no SQL,
   no relational schema, no shared code with the server-side SQLite.
   Query capability was limited to primary-key lookup.
2. **The Pi still needed Node.js + Puppeteer + Chromium** to bootstrap
   the "browser node." Not a real browser tab — a scripted headless
   Chromium controlled by Node.js. Couldn't run on iOS, couldn't run
   on a locked-down Chromebook, couldn't run without a host OS capable
   of spawning Chromium processes.
3. **No shared protocol code between edge and server.** The edge ran
   JS + IndexedDB, the server ran Node.js + Express + in-memory state.
   No HMAC chain, no byte-identical event log, no audit trail that
   could be verified on both sides.

v3.0 browser-node is the direct continuation of that thesis path,
using the 2024–2025 technology stack that finally closes the three
gaps above:

- **OPFS + SQLite WASM** replaces IndexedDB → real relational schema,
  shared DDL with native server, SQL queries instead of blob scans
- **Go WASM** replaces Node.js + Puppeteer → the browser tab *is* the
  node, no host-side runtime required, runs on iOS Safari 17+
- **Same `core/` Go package** compiles for both native server and
  browser → HMAC event chain is byte-identical by construction, not
  "mostly compatible"

**Success criterion for v3.0**: match the thesis's latency and
throughput numbers (2 ms LAN, 40 ms WAN, 60fps sustained write
throughput) with *none* of the host-side dependencies. If a browser
tab on an iPhone can do what a Raspberry Pi with Chromium + Puppeteer
+ Node.js did in 2023, v3.0 is a win — not because it's faster, but
because it's universal.

The thesis also anticipated this trajectory. Chapter 5 "Future Work"
lists three items, in order:

1. Edge devices should support independent local configuration and
   survive backend failures
2. The backend should store no media-adjacent content, only user
   and resource metadata
3. Scale-out should come from P2P topology, not from centralized
   media servers

v3.0 browser-node makes all three structurally true, not by policy
but by architecture. The tab owns its own `universe.db`. The backend
is optional. Peers find each other over WebRTC. The thesis was the
proof-of-concept; elastik 3.0 is the generalization.

## Contemporary Work

The browser-as-sovereign-node thesis is not being pursued alone.
Parallel to elastik's v3.0 design, an independent project arrived at
the same conclusion from a different axis:

**AI Grid** by Ryan Smith (February 2026, aigrid.soothsawyer.com) —
"turns every browser tab into a node in a distributed AI cluster."
Stack:

- **WebGPU** for GPU acceleration, now treated as infrastructure-level
  compute surface rather than a graphics API
- **WebLLM** for in-tab large language model inference — no server,
  no Docker, no cloud
- **P2P mesh** over WebRTC for direct browser-to-browser compute
  sharing; tabs can contribute spare GPU cycles to a shared network
- **Browser sandbox as the trust boundary** — no container runtime,
  no OS-level isolation needed
- Entry cost: "a URL and whatever graphics card happens to be sitting
  in your laptop"

### Why the Compute Layer Is More Than WebGPU

AI Grid picks WebGPU because in early 2026 it's the only broadly
shipped compute surface in browsers. But the compute layer has
multiple axes, and a production distributed AI runtime has to talk
to all of them:

| API | Role | Targets |
|---|---|---|
| **WebGPU** | General GPU compute (shaders, kernels, matmul) | Any discrete or integrated GPU |
| **WebNN** | Hardware ML inference abstraction | Apple ANE, Windows DirectML, Intel NPU, Qualcomm Hexagon, Google TPU |
| **WASM SIMD / threads** | CPU-side tensor fallback | Everything else |
| **WASI-NN** (future) | Server-side ML API, same shape as WebNN | Native runtimes |

WebGPU gives you "browser can drive any GPU." WebNN gives you
"browser can drive **any dedicated AI silicon**" — the ANE chip on
an iPhone runs int8 inference 3–5× faster than that same phone's
GPU and at a fraction of the power draw. On Windows laptops with
Intel/Qualcomm NPUs the gap is larger. WebGPU is the portable
compute floor; WebNN is the hardware ceiling.

In early 2026 WebNN is still behind an origin trial in Chrome and
under active spec work, which is why AI Grid ships on WebGPU today.
But the architectural conclusion is unchanged: **the browser already
has APIs to reach every kind of compute hardware on the device**.
Graphics card, NPU, ANE, CPU SIMD — all of them are addressable
from inside the sandbox, no native install, no driver, no root.

This matters for the protocol layer (next section) because a
distributed AI coordinator can't assume one compute runtime. The
same task might be handed to a tab with WebGPU, another with WebNN,
another with plain WASM — and the coordinator has to route
accordingly.

### Three Axes, One Thesis

This matters because AI Grid and elastik v3.0 are **orthogonal axes
of the same thesis**:

| Axis | Project | Year | Proves |
|---|---|---|---|
| Transport + on-device inference | 2023 thesis (WebRTC + TF.js PoseNet) | 2023 | Browser tab can stream and infer |
| **State + protocol sovereignty** | **elastik v3.0 (Go WASM + OPFS SQLite)** | **2026** | **Browser tab can own its database and audit chain** |
| Compute + model sovereignty | AI Grid (WebGPU/WebNN + WebLLM + mesh) | 2026-02 | Browser tab can run LLMs and share hardware-accelerated compute |

Three independent projects, three years, three teams, all converging
on the same architectural endpoint: **the browser tab is a complete
sovereign node** — transport, state, compute, storage, all inside
the sandbox, no host runtime required.

### elastik IS the Protocol Layer AI Grid Needs

The previous draft of this section said "elastik v3.0 and AI Grid
are two things we might combine." That undersells it. The accurate
framing is sharper:

> **Every browser-native distributed AI project needs a protocol
> layer for task dispatch, result collection, chained audit, and
> cross-session persistence. elastik is that protocol layer.**

The same way a web app doesn't reinvent HTTP, a browser-distributed
compute project shouldn't reinvent task dispatch, provenance,
signing, and persistence. Those concerns are upstream of any
particular compute runtime (WebGPU, WebNN, WASM) and upstream of
any particular model (WebLLM, ONNX, custom kernel). They belong in
a layer underneath.

elastik's existing protocol primitives map point-for-point to what
a distributed AI coordinator needs:

| Distributed AI Need | elastik Primitive |
|---|---|
| Addressable nodes | `world` (per-tab or per-peer namespace) |
| Task dispatch | `POST /{world}/pending` |
| Result collection | `POST /{world}/result` |
| Current-state read | `GET /{world}/read` |
| Ordered provenance | `events` table, HMAC-chained |
| Cross-session persistence | OPFS + SQLite (v3.0) or native SQLite (v2.x) |
| Tamper-evident audit | Signed chain, any peer can verify |
| Language-neutral implementation | Go (native) + Go WASM (browser), same source |

What's missing for a real distributed-AI runtime is one field:
**a declared runtime type on the task**. `pending_js` today is
implicitly "JS in an eval/function sandbox." A worker receiving
the task needs to know: is this JS, a WebGPU compute kernel, a
WebNN graph descriptor, a WASM module URL? Workers must decline
tasks whose runtime they can't host.

### The v3.1 Protocol Extension: Runtime Tagging

The fix is backward-compatible. Add one optional field alongside
`pending_js`:

```
stage_meta
  pending_js       TEXT         -- the task payload (unchanged)
  pending_runtime  TEXT         -- NEW: "js" (default) | "wasm" | "webgpu" | "webnn" | ...
  pending_spec     TEXT         -- NEW: optional JSON with resource hints
                                  (model size, input shape, precision, timeout)
```

Workers advertise their runtime capabilities on connect. Coordinator
matches tasks to capable workers. Unknown runtimes → the task
falls back to the worker pool that explicitly advertises support,
or stays pending until one shows up.

Default `pending_runtime = "js"` keeps every v2.x client working
unchanged — no migration, no break.

### The Compute Delegation Flow

```
 coordinator tab                                worker tab
      │                                              │  (advertises: webgpu, js)
      │  POST /{world}/pending                       │
      │  body    = "<webgpu compute kernel source>"  │
      │  runtime = "webgpu"                          │
      ├─────────────────────────────────────────────→│
      │                                              │  poll /{world}/read
      │                                              │  → sees pending_js + webgpu
      │                                              │  → dispatches to GPU pipeline
      │                                              │
      │  POST /{world}/result                        │
      │←─────────────────────────────────────────────┤
      │  (HMAC-chained event: runtime,               │
      │   duration, peer_id, model, tokens)          │
```

Every step is HMAC-signed. Every step appears in the `events`
table. An auditor weeks later can walk the chain and prove: *tab X
asked tab Y to run kernel K, tab Y did it on WebGPU backend B in T
milliseconds, here is the signed receipt*.

### What This Means for AI Grid-class Projects

A project like AI Grid, in this framing, is **an elastik client
with a WebGPU/WebNN runtime adapter**. Its mesh layer becomes:
worker tabs connect to the elastik protocol over HTTP (native) or
direct DB access (browser node), advertise runtimes, pull tasks,
push results. The mesh's transport is WebRTC DataChannel, but the
*protocol spoken over that channel* is elastik's HTTP-shaped
verbs: pending, result, read.

This is the same move HTTP made for web apps in the 90s. The
browser-AI layer is at that moment now. Either it converges on a
shared protocol — which is elastik's thesis — or every project
reinvents the same primitives badly, and nothing composes.

### The Complete Sovereign Tab

A browser tab running elastik v3.0 plus a runtime adapter of its
choice becomes:

- **Protocol-sovereign** — owns its HMAC chain and SQLite state
- **Compute-sovereign** — dispatches to local WebGPU/WebNN/WASM, or
  routes to peers that can host the requested runtime
- **Storage-sovereign** — OPFS persistence, survives reload
- **Transport-sovereign** — WebRTC direct peering, no relay unless
  NAT forces it
- **Model-sovereign** — ships its own weights or pulls them P2P,
  never phones home

No cloud. No Docker. No VPS. No login. A URL.

This is the endgame the 2023 thesis pointed at. elastik supplies
the coordination protocol. Runtime adapters (WebGPU, WebNN, WASM)
supply the compute. The mesh supplies the transport. Together they
form a complete distributed runtime where the unit of deployment
is a browser tab and the unit of coordination is a signed event in
an append-only log.

## The Goal

A browser tab should be able to run a complete elastik protocol node — not a
client talking to a server, but the server itself. Same SQLite schema. Same
HMAC chain. Same world CRUD. Same code, compiled twice.

## The Stack

```
┌───────────────────────────────────────────────────────────┐
│ UI layer (JS)                 — glue only                 │
├───────────────────────────────────────────────────────────┤
│ Go WASM       — protocol logic (CRUD, HMAC, chain verify) │  ← same source as native
│ SQLite WASM   — database engine (C → WASM)                │
│ OPFS          — persistent storage (sync I/O)             │
├───────────────────────────────────────────────────────────┤
│ WebRTC        — native C++  → peer transport              │
│ Web Crypto    — native      → hashing, signing            │
│ WebGPU        — native      → GPGPU compute (any GPU)     │
│ WebNN         — native      → hardware ML (NPU/ANE/etc.)  │
│ WASM SIMD     — native      → CPU tensor fallback         │
└───────────────────────────────────────────────────────────┘
```

JS does glue only. Every expensive operation runs in WASM or native
browser APIs. The compute row has **three parallel backends**, not
one: the `pending_runtime` field on a task tells workers which row
to dispatch to. A tab with a beefy GPU advertises WebGPU; an iPhone
advertises WebNN (routes to ANE); an old laptop falls back to WASM
SIMD. Same protocol, heterogeneous hardware.

## Why OPFS Changes Everything

Before OPFS, browser persistence meant IndexedDB — async, key-value, not a
relational database. Running SQLite in the browser meant keeping everything
in memory, or slow async writes through IDB.

OPFS (Origin Private File System) is different:
- Real file system API, private per origin
- `createSyncAccessHandle()` — synchronous reads and writes
- SQLite's official WASM build supports OPFS natively
- Chrome, Edge, Firefox, Safari 17+ — all ship it
- Production-proven (Notion uses OPFS + SQLite)

Performance, measured honestly:
- WASM itself: ~90% of native
- OPFS sync access: ~1ms write latency (vs IndexedDB ~3ms+)
- Web Worker message serialization: ~4ms overhead per call
- **Overall: 70-80% of native SQLite on disk**

Not "indistinguishable from native." But 3-4× faster than IndexedDB, and
fast enough that elastik's `universe.db` (usually <10 MB) is never the
bottleneck.

## Isomorphic Compilation

One `core/` package in Go. Two compile targets:

```bash
# Native server
go build -o elastik-lite ./native

# Browser node
GOOS=js GOARCH=wasm go build -o elastik.wasm ./wasm
```

Both link the same `core/` package:

```go
// core/world.go — pure logic, no I/O
func WriteWorld(db DB, name, content string) (version int, err error) {
    // ... same code runs both sides
}

func LogEvent(db DB, action, body string) error {
    // ... same HMAC chain algorithm, byte-for-byte
}
```

The `DB` interface has two implementations:
- `native/db_sqlite.go` — wraps `modernc.org/sqlite` via `database/sql`
- `wasm/db_opfs.go` — wraps SQLite WASM via `syscall/js`, backed by OPFS

What you get from this:
1. **HMAC chain consistency** — if the server signs, the browser validates,
   both run the exact same function. Not "should match" — byte-identical AST.
2. **Schema consistency** — DDL is a `const` in core. Compiled once. Cannot drift.
3. **Type safety across the boundary** — `World.Version int` is the same struct
   on both sides. No Python-style `world["version"]` runtime guessing.

Python cannot do this. Pyodide can run Python in the browser but ships a
full CPython interpreter (~15 MB). Go WASM compiles the code itself.

## The Three Real Gotchas

### 1. SharedArrayBuffer requires COOP/COEP headers

OPFS's synchronous VFS needs `SharedArrayBuffer`, which browsers only expose
when the page is served with:

```
Cross-Origin-Opener-Policy:   same-origin
Cross-Origin-Embedder-Policy: require-corp
```

Miss either header, `SharedArrayBuffer` is unavailable, OPFS VFS fails to load.

**Workaround**: `coi-serviceworker.js` injects these headers from inside the
Service Worker, no backend changes required. elastik already ships a Service
Worker — just extend it.

### 2. Concurrent writes corrupt the database

Notion hit this in production: two tabs writing the same OPFS-backed SQLite
file → file corruption → users see wrong data.

**elastik is immune** because of the single-tab-single-world model. Each
universe.db is owned by one tab. Cross-tab coordination happens through
WebRTC DataChannels, not shared storage.

If we ever do need multi-tab, the rule is: one Web Worker holds the
connection, other tabs message it.

### 3. OPFS sync API is Worker-only

`createSyncAccessHandle()` only works in Web Workers. The main thread can't
touch OPFS synchronously.

**Architecture implication**: the Go WASM module runs in a dedicated Worker.
Main thread just forwards requests via `postMessage`. This is fine —
elastik's HTTP-style request/response model maps cleanly onto messages.

## Safari Quirk

Safari 16.x: OPFS exists but has bugs. SQLite WASM docs explicitly list
it as incompatible.

Safari 17+: fixed, but requires the **sahpool VFS** (Storage Access Handle
Pool) instead of the standard OPFS VFS. Slightly slower but works.

elastik's existing tier detection handles this:

| Tier | Browser | Storage | Speed |
|------|---------|---------|-------|
| 1 | Chrome, Edge | Standard OPFS VFS | Best |
| 2 | Safari 17+ | sahpool VFS fallback | Slightly slower |
| 2 | Firefox | OPFS with minor limits | Good |
| 3 | Older browsers | IndexedDB fallback | Slowest, still works |

Tier 1 gets the full experience. Tier 3 still runs the protocol, just slower.
No tier is excluded.

## Where This Fits in the Roadmap

**2.0 (shipped)** — Python split, secure boot, shape constraints doc

**2.x (next)** — Go Lite. Native binary, single-file distribution.
Architectural discipline: `core/` package is pure, no `net/http`, no
`database/sql` directly. Everything I/O behind interfaces. This is the
groundwork for 3.0.

**3.0 (this document)** — Browser node. Compile the same `core/` to WASM,
back it with SQLite WASM + OPFS, run it in a dedicated Worker. A browser
tab becomes a full elastik node that can sync with other nodes over WebRTC
using the same protocol code the server runs.

## Pre-3.0 Validation Spikes

Three spikes to run before committing to 3.0. Each ~1 day:

1. **TinyGo vs Go bundle size** — compile `core/` with both. Decide which
   toolchain the WASM target uses. TinyGo gives 10× smaller output but loses
   parts of stdlib. Need to verify `core/` dependencies fit.

2. **SQLite WASM + OPFS integration** — minimal prototype: open a DB, write
   a row, close, reopen, read it back. Measure binary size and first-write
   latency.

3. **Worker message bridge** — 50 lines of JS glue: main thread
   `postMessage` → Worker → Go WASM → SQLite WASM → OPFS → reply. End-to-end
   latency measurement.

All three green → 3.0 is mechanical translation work.
Any one blocked → redesign before committing.

## The Point

Browser-as-node is not a metaphor anymore. With Go WASM + SQLite WASM +
OPFS + WebRTC, a tab can run the same protocol code as the server, with
the same types, reading the same schema, signed with the same HMAC chain.
No translation layer. No "mostly compatible." Compiler-guaranteed identical.

This is what "AI-native OS in the browser" means at the implementation
level. Not marketing. Load-bearing architecture.
