# Why Go + Python + JS

Three languages. Not by accident. Each survives where its peers die.

## Three survival strategies, three failure modes

Every language survives by one of three strategies. Each strategy has a
failure mode that kills most languages that attempt it.

### Brute force: compile and carry everything

The strategy: static binary, zero runtime dependencies, runs anywhere.

**Failure mode: dynamic library dependency.**
C/C++ claim self-sufficiency but lean on glibc, libstdc++, platform SDKs.
Cross-compile a C program for six platforms — you'll meet six different
linker hells. Rust improves on this but cross-compilation remains complex.

**Go avoids it.** `GOOS=linux GOARCH=arm64 go build` — one line, six
platforms. Static linking by default. No libc. The binary IS the
deployment. Not a warlord pretending to be independent — actually
independent.

### Assimilation: become part of the environment

The strategy: plain text, runs in any terminal, no install ritual.

**Failure mode: cross-environment mutation.**
Bash is text, but Dash/Ash/Zsh behave differently. A bash script that
works on Ubuntu may break on Alpine (no bash) or macOS (BSD coreutils).
The language mutated with each host until there were four different
Bashes. Ruby assimilates too, but then needs gems.

**Python avoids it.** `python server.py` behaves the same on Windows,
macOS, Linux, Termux, a-Shell. No platform-specific mutation. Python 3.8+
is Python 3.8+ everywhere. The stdlib covers HTTP, JSON, SQLite, crypto
without touching pip.

And zero pip means zero supply chain attack surface. In twelve days of
March 2026, a North Korean state hacking group (Sapphire Sleet) poisoned
five projects in sequence: Trivy (Mar 19) → KICS (Mar 23) → LiteLLM
(Mar 24) → Telnyx (Mar 27) → Axios (Mar 31). PyPI and npm fell
simultaneously. LiteLLM: 97M monthly downloads, credentials harvested,
entire K8s clusters compromised. Axios: 100M weekly downloads, npm's
most popular HTTP client — `npm install` and within two seconds a
cross-platform RAT was phoning Pyongyang.

The attack surface is your supplier's supplier's supplier. Axios wasn't
directly compromised — a security scanning tool was poisoned first,
which leaked a maintainer's publishing credentials, which published the
malicious version. Three degrees of separation, all invisible.

elastik's exposure to this entire twelve-day campaign: **zero.**

```
Python: zero pip dependencies. stdlib only.      → not in PyPI ecosystem
Go:     static binary. go.sum hash lock.          → no postinstall scripts
JS:     78 lines. fetch, not axios. zero npm.     → no node_modules
```

`fetch` is a browser built-in. No install, no trust chain, no attack
surface. elastik uses `fetch` not because it's better than axios — but
because it doesn't require `npm install`. The safest dependency is no
dependency. Not laziness — survival.

### Parasitism: live inside a larger host

The strategy: embed in a ubiquitous runtime, ride its distribution.

**Failure mode: host too small.**
Lua is the perfect parasite — tiny, embeddable, zero overhead. But it
lives inside game engines. How many game engines? A few. How many users?
Millions, not billions. Java Applets parasitized browsers — then browsers
killed the host.

**JS avoids it.** The host is the web browser. Billions of devices. The
host is not going away. The host grows every year. JS doesn't need an
install, a runtime, or a package manager. Open a browser — it's there.

## The lock-in test

One more filter: does the language exist to free you or to trap you?

Swift is a good language. But it exists so you stay inside Apple's walls.
The deeper you go, the harder it is to leave. That's not a side effect —
it's the design goal. Kotlin is the same, Google's version.

Go was created by Google but doesn't lock you into Google. Python — most
people forgot who created it. JS is standardized by W3C/ECMA, owned by
no one.

**Guard languages vs. free languages.** Guards fight for their master.
Free languages fight for their user.

## Why these three together

| Strategy     | Failure mode               | Failed by              | Avoided by       |
| ------------ | -------------------------- | ---------------------- | ---------------- |
| Brute force  | Dynamic library dependency | C, C++, Rust (complex) | **Go**     |
| Assimilation | Cross-environment mutation | Bash, Ruby             | **Python** |
| Parasitism   | Host too small or mortal   | Lua, Java Applets      | **JS**     |

Not "three languages that happen to work." Three languages that each
avoid the fatal flaw of their category. Go avoids C's dynamic linking.
Python avoids Bash's platform mutation. JS avoids Lua's tiny host.

## Personal context

I've been on both sides.

**SemiDrive SoC** — C++ on a proprietary DRM/KMS pipeline.
Linux, but modified Linux. Optimize ETC texture compression for one chip —
switch chips, start over. The code is hostage to the silicon vendor.

**Siemens LOGO! PLC** — Four expansion slots, all full. Want a
fifth? Buy a new module. Siemens pricing. Want to switch platforms?
Relearn everything, rebuy everything, reconfigure everything. The ceiling
is four slots and a catalog.

**FPGA** — Verilog on Questa (Mentor/Siemens EDA). License
costs five figures per year. University paid for it. After graduation?
The toolchain disappears.

Every pain is the same pain: **vendor lock-in at the infrastructure
layer.** The chip vendor owns your display pipeline. The PLC vendor owns
your I/O count. The EDA vendor owns your ability to simulate.

Then I found the web. Nobody owns HTTP. Nobody owns the browser. Nobody
owns JS. Same act of programming — completely different freedom.

## The escape route

When the PLC hit its ceiling, I didn't replace it. I put a
Raspberry Pi next to it. Pi runs Python, runs elastik, runs AI. The PLC
does what PLCs do — relay control, I/O. The Pi does the intelligence
layer. `HTTP POST` bridges them.

This is elastik's strategy for embedded: **don't go down, stand beside.**
MCUs control relays. elastik receives their data. The MCU doesn't run
elastik — it feeds elastik. One POST. That's the entire integration.

## Three uprisings

1. **OS unified hardware.** Chip dialects became standard driver
   interfaces. Applications stopped caring about hardware.
2. **Browser unified OS.** Windows/Mac/Linux all have browsers.
   WebRTC/WebGPU/IndexedDB — JS stopped caring about OS.
3. **elastik unifies AI.** Ollama/Claude/GPT all accept POST.
   Local/cloud/edge — all strings. Applications stop caring about
   AI backend.

Each uprising: an abstraction layer suppresses the warlords beneath it.

Go + Python + JS are the weapons. All three are free armies, not palace
guards. Below is a battlefield. Ahead is freedom.

## What happens when you don't choose

Microsoft's GUI history is a cautionary tale. 14 direction changes in 14
years. 17 GUI frameworks coexisting across 5 languages. Not because the
technology was bad — WPF was genuinely impressive. They died because
internal politics killed them. Every VP needed their own "strategic
project." Every two years, the previous team's work was declared legacy.

Jeffrey Snover (Microsoft CTO, 23 years at the company) called it out:
at //Build 2012, six teams competed for developer attention
simultaneously. WinRT, WPF, HTML+JS, C++, Metro, .NET — all "the
future" at the same time. Developers watched, picked Electron, and left.

Charles Petzold — the man who wrote *Programming Windows*, the 852-page
bible — stopped updating after the 6th edition. When your most faithful
evangelist walks away, the ecosystem is already dead.

**The living specimen:** Outlook on Windows. Plug the same laptop into a
1080p monitor and a 2K monitor. On 1080p: the delete icon becomes a
chunky aliased cross, classic style, with a red flag badge. On 2K: clean
modern icons, no flag. Same app. Same OS. Same machine. Different
resolution triggers different rendering paths — GDI fallback here, WPF
there, WinUI somewhere else. 17 GUI frameworks in one app, visible by
switching a cable.

This is what happens when a platform breaks its promise 14 times.
Developers can tolerate an imperfect API. They cannot tolerate the fear
of starting over every two years.

elastik's answer: 210 lines of Python. Five rules. No framework. The
protocol hasn't changed since day one. If it runs today, it runs in five
years. Not because we're disciplined — because there's nothing to change.

## CouchDB: the direct ancestor

CouchDB (2005) and elastik share the same thesis:

- HTTP is the only interface
- Documents are JSON (elastik: strings)
- Offline-first
- Sync between nodes
- Append-only storage
- Philosophy: do less, relax

Damien Katz saw all of this twenty years ago. He was right about everything.

### What elastik cut

| CouchDB | elastik | Why |
|---------|---------|-----|
| MapReduce query engine | nothing | Scope is narrower — human-AI string protocol, not a database |
| Conflict trees | Higher version wins | Good enough for single-user + AI |
| Replication protocol | Incremental sync | No multi-master, no merge |
| Erlang runtime | Python + Go | Distribution story is simpler now |
| Tens of MB deployment | 210 lines | See above |

CouchDB is a complete database. elastik only kept the pipe.
Same idea, cut to different depths.

### Why he couldn't cut deeper

The browser in 2005:

- No `fetch` — `XMLHttpRequest` only
- No `JSON.parse` — you called `eval(responseText)`
- No WebSocket — polling via iframe hacks
- No `localStorage` — cookies, 4KB limit
- No CORS — cross-origin requests blocked
- IE6 at 70% market share — write everything twice
- JS engines too slow for real computation — V8 arrived in 2008

Saying "browser talks directly to the database" in 2005 was like
riding a bicycle onto a highway that hadn't been built yet.
The bicycle wasn't wrong. The road wasn't ready.

### What he did anyway

- Chose Erlang when Go didn't exist (2009) — best concurrency option at the time
- Insisted on HTTP-as-API when nobody had `fetch` — ahead of the industry
- Built offline sync when WebRTC didn't exist (2011) — ahead of the industry
- Said "HTTP is fast enough" when everyone said it was too slow — ahead of the industry

He got the vision right. The toolchain didn't support it yet.

### What time gave us

| Tool | Year | What it unlocked |
|------|------|-----------------|
| Go | 2009 | Single-binary distribution, no runtime |
| WebRTC | 2011 | Browser-to-browser, no server |
| V8 / modern JS | 2008+ | Browser became capable |
| Browser as OS | 2020s | localStorage, WebGPU, service workers |
| AI coding assistants | 2023 | One person can write the whole stack |
| Ollama | 2023 | Local AI, no API keys |
| npm/PyPI supply chain attacks | 2024-2026 | Validated zero-dependency |

None of these were invented here. They were given by the era.
What we did was recognize them at the right time.
Recognition isn't nothing — but it isn't invention either.

### The honest version

If we had started in 2005, we would probably have chosen Erlang too.
We would have added MapReduce too. We would have died in the same place.

The difference isn't vision. The vision is the same. The difference
is twenty years.

Damien Katz built the right thing with the wrong era's tools.
We built the same thing with the right era's tools.

He used Erlang in the IE6 era. We used Go in the WebGPU era.
Not smarter — later. Respect where it's due.
