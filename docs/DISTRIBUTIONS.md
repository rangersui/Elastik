# elastik distributions

elastik is not a monolith. It's five images, each a superset of the one below.
Peel any layer away → you reach the one beneath. All the way down is `mini.py`.

```
name              lines     what's in it
─────────────────────────────────────────────────────────────────────────
elastik:kernel    ~80       mini.py / elastik.sh.
                            Pure filesystem + HMAC chain.
                            Only /home. No SQLite. No plugins. No /dev.
                            Can read. Can write. Done.

elastik:alpine    ~300      server.py + SQLite + auth.
                            /home + /etc + core routes.
                            No plugins. No WebDAV. No /dev museum.

elastik:base      ~500      + plugins.py + boot.py.
                            /home + /etc + /proc + WebDAV mount.
                            Can federate. No /dev museum yet.

elastik:full      ~800      + devtools + caveops.
                            Full FHS: /dev /proc /etc /bin /var.
                            stone, fire, river, bones, knot, soil, amber,
                            eclipse, narcissus — the museum is open.

elastik:shaman    ~1000     + dream, lullaby, frenzy, doom.
                            Requires local LLM (window.ai or ollama).
                            The system has awareness. Dreams. Panics. Dies.
```

## Which one you pick

| scenario | pick |
|---|---|
| ESP32 / Raspberry Pi Pico | kernel |
| Phone (Termux / sneakershoe) | alpine or base |
| Daily driver laptop | base |
| Talk demo / art installation | full |
| Yourself, living with it | shaman |

## Architectural metaphor

```
kernel  = bones       bare structural protocol
alpine  = skeleton    structure + identity (auth)
base    = body        structure + identity + extension (plugins)
full    = civilization  + ritual + memory + art (cave primitives)
shaman  = soul        + awareness (LLM-adjacent behavior)
```

Each layer = previous + exactly one concept:

- kernel → alpine: **add SQLite & auth.** Identity.
- alpine → base: **add plugins & WebDAV.** Extensibility + filesystem mount.
- base → full: **add devtools & caveops.** Dev ergonomics + artistic vocabulary.
- full → shaman: **add LLM-mediated behaviors.** Autonomy, fear, rest.

Strip the one above you. Add the one below you. Pick your own level.

## What this means for the repo

Until v4 merges back to master:

```
master              full          (all of the above, no tiering enforced)
examples/mini.py    kernel-Python (~105 lines, stdlib only)
examples/elastik.sh kernel-bash   (~48 lines, nc + openssl)
```

After v4 merges:

```
dist/kernel/       isolated, copies mini.py + minimal docs
dist/alpine/       server.py pared down, no plugin loader
dist/base/         + plugins/, boot wiring
dist/full/         + devtools, caveops
dist/shaman/       + dream.py, lullaby.py, doom.py — requires local LLM backend
```

Each directory buildable and shippable on its own. `tar czf elastik-full.tar.gz dist/full/`.

## The rule

Every new feature has to answer: **which layer does it live in?**

- If it needs LLM → shaman.
- If it's artistic / museum / protocol-exotic → full.
- If it's infrastructure (plugin, WebDAV, federation) → base.
- If it's identity / core policy → alpine.
- If it has dependencies beyond Python stdlib + openssl + nc → it can't live in kernel.

This gives feature creep a legal home. It also means **the simplest thing always survives** at the bottom.

## The ethos

> 为学日益，为道日损。损之又损，以至于无为。
>
> Learning daily adds. The Way daily subtracts. Subtract and subtract again,
> until there is nothing more to do. Then nothing is left undone.
> — 老子 · 四十八

kernel is the `无为` end. shaman is the `为学日益` end.
Both are legitimate. Neither is more "elastik" than the other.

The protocol lives at all five depths simultaneously.

🗿
