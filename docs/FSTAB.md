# elastik — a Linux machine whose interface is curl

## One sentence

You have a Linux machine whose interface is curl.

## Directory structure

```
/
├── home/           user data — worlds you own
│   ├── work
│   ├── study
│   └── {user}/
├── dev/            devices — behavior, not storage
│   ├── stone       receives, remembers, never replies (204)
│   ├── fire        burns on contact, leaves /ash
│   ├── river       global event stream (SSE)
│   ├── sleep       sovereign rest — all routes return 503
│   ├── null        swallow, discard
│   ├── void        silent socket kill (444)
│   ├── fast        full stomach — refuses writes (413)
│   ├── glacier     returns 1 byte/sec — patience required
│   ├── scale       new data must weigh same as old (411)
│   ├── lethe       stores then forces you to forget (205)
│   ├── frenzy      too fast — calm down (420)
│   ├── doom        60s countdown, then SIGALRM (kill)
│   ├── lullaby     heartbeat stream ·····♩··♩·····
│   ├── dream       random fragments from all worlds (only during /dev/sleep)
│   ├── scar        every 500 error, logged as a wound
│   └── womb        new worlds need 10min gestation (425)
├── etc/            system configuration — read free, write needs approve
│   ├── fstab       this file. directory semantics.
│   ├── passwd      username:permission mappings
│   ├── shadow      token hashes (chmod 000 — unreadable)
│   ├── motd        moaisay greeting on login
│   ├── actions     allowed plugin actions whitelist
│   ├── cdn         CDN/asset configuration
│   ├── endpoints   federation target mappings
│   ├── sync        sync configuration
│   ├── peers       known federation nodes
│   └── cron        scheduled plugin tasks
├── proc/           runtime state — zero storage, computed on read
│   ├── pid         os.getpid()
│   ├── uptime      seconds since boot
│   ├── host        hostname + platform + python version
│   ├── pulse       write rate last 60s as ASCII sparkline ▁▃▁▁█▇▃▁
│   ├── load        requests per second last 60s
│   ├── weight      total bytes across all worlds
│   ├── worlds      all world names + version + size
│   ├── peers       connected federation nodes (live)
│   ├── birth       first-ever boot timestamp
│   └── ancestor    git log — the family tree
├── bin/            core commands — devtools routes
│   ├── grep        search worlds. ?q=error&mode=l
│   ├── tail        last n lines. ?world=x&n=10
│   ├── head        first n lines. ?world=x&n=10
│   ├── wc          word/line/byte count. ?world=x
│   ├── rev         reverse each line (UTF-8 torture test)
│   ├── echo        return body unchanged
│   ├── cat         alias for /{world}/read
│   ├── true        always 200
│   ├── false       always 403
│   ├── yes         returns 'yes' n times
│   ├── cowsay      encoding test
│   └── moaisay     🗿
├── usr/
│   └── lib/        shared components
│       ├── skills/         AI skill definitions
│       │   ├── core
│       │   ├── patch
│       │   ├── renderer
│       │   ├── security
│       │   ├── sync
│       │   ├── translate
│       │   └── dom-patch
│       └── renderer/       HTML renderers
│           ├── markdown
│           ├── cockpit
│           ├── dashboard
│           ├── sparkline
│           └── json-tree
├── var/
│   ├── log/        event logs — append-only
│   │   ├── sync        sync event log
│   │   ├── alerts      system alerts
│   │   ├── sensors     sensor data log
│   │   └── scar        crash/error log (wounds)
│   └── spool/      queues — consume after read
│       ├── tasks       pending tasks
│       ├── proposals   plugin proposals awaiting approval
│       └── pending     pending_js execution queue
├── mnt/            mount points
│   └── webdav      WebDAV mount — Finder/Explorer sees this as filesystem
├── tmp/            ephemeral
│   └── dew         data that dies every hour
└── lost+found/     recovered data
    └── .trash/     tombed worlds — chmod 000, need sudo to exhume
```

## Auth model

```
HTTP Basic Auth: Authorization: Basic base64(user:token)
curl -u ranger:token localhost:3005/home/work/read

/etc/passwd     user:tier mappings (T1 read / T2 write / T3 approve)
/etc/shadow     token hashes — chmod 000, unreadable via any route
```

Two tiers, same as Unix:
- Regular user (read token) → read any world, use /bin commands
- Root (approve token) → write, delete, /tomb, /meteor, /dev/sleep, /dev/doom

## Filesystem table (/etc/fstab)

```
# path          type        permissions              description
/home/*         world       read: T1, write: T2      user data
/etc/*          config      read: T1, write: T3      system config
/proc/*         virtual     read: T1, write: never   computed on access
/dev/*          device      use: T1/T2               behavior, not storage
/bin/*          command     exec: T1                 unix pipe primitives
/usr/lib/*      library     read: T1, write: T3      shared components
/var/log/*      log         read: T1, append: T2     event records
/var/spool/*    queue       read: T1, consume: T2    pending work
/tmp/*          ephemeral   read: T1, write: T2      auto-expires
/lost+found/*   recovery    read: T3 (sudo)          tombed data
```

## Primitive routes — the museum

Human information primitives, implemented as HTTP routes.

```
# storage semantics
/dev/stone      remember but never speak              POST→204
/wall           public record, append-only             POST→200
/amber          zlib+base64+chmod 400, sealed forever  POST→200
/knot           discard content, tie knot by size       POST→200 GET→rope
/trail          append coordinates, one-way history     POST→200

# destruction semantics  
/dev/fire       burn, leave hash in /ash               POST→200
/tomb           bury, chmod 000, write epitaph          POST→200
/meteor         kill all but one random survivor        DELETE→207
/soil           bury, decay 1 byte/hour                 POST→200 GET→decayed
/dev/lethe      store then force-forget (205)           POST→205

# time semantics
/seed           locked for 15 days, then sprouts        POST→200 GET→423/200
/dew            dies every hour                         POST→200 GET→410 after :00
/glacier        returns 1 byte/sec                      GET→200 (slowly)
/shadow         length varies by time of day, 403 at night  GET→200/403
/moss           neglected worlds grow ░ characters       GET→200
/bloodline      TTL decreases on each read               GET→200 until TTL=0→fire

# divination semantics
/bones          SHA-256 oracle — 吉/凶                   POST→200
/hunt           random world                             GET→200
/narcissus      fuzzy-match your own past words           POST→200
/dev/dream      random fragments, only during /dev/sleep   GET→200

# social semantics
/drum           broadcast, no history, miss it = gone     POST→200 (SSE push)
/offering       one-way transfer, sender emptied          POST→200
/chant          requires 3 simultaneous POSTs              POST→406/201

# system lifecycle
/dev/sleep      all routes → 503 for N hours              POST→503
/dev/fast       refuses writes when full (24h/2MB)         POST→413
/dev/doom       60s countdown then system dies             POST→200→death
/dev/frenzy     too many requests → screen goes red (420)  GET→420
/dev/menopause  100 worlds max, then no more creation      POST→405
/tattoo         permanently alters UI CSS                   POST→200
/dev/scar       auto-logs every 500 error                  GET→200
/dev/birth      first boot timestamp                       GET→200
/dev/ancestor   git log — the family tree                  GET→200

# remains
/ash            hashes of burned data                     GET→200
/fossil         first+last line of fully decomposed data   GET→200

# ceremony
/moaisay        🗿 speaks                                 GET/POST→200
/dev/lullaby    heartbeat stream ·····♩··♩·····           GET→SSE
```

## Transport

```
curl            HTTP — the universal interface
WebDAV          mount as filesystem in Finder/Explorer
Unix pipe       curl | jq | curl — 1973 technology
SSE             /dev/river, /dev/lullaby, /stream/{name}
Cloudflare      tunnel for remote access — phone as server
```

## Storage

```
SQLite          universe.db — one file per world
                stage_meta: stage_html, version, hmac, ext
                events: append-only audit log
                HMAC chain: every write signed, not a database — a notary

Alternative     pure filesystem (mini.py, 80 lines)
                worlds/{name}/content + worlds/{name}/meta.json
                atomic write via os.replace()
                no SQLite, no dependencies
```

## Identity

```
curl -u ranger:token localhost:3005/home/work/read     ← HTTP Basic Auth
curl -u ai:readtoken localhost:3005/proc/uptime         ← AI with limited perms

/etc/passwd     ranger:T3
                ai:T1
                colleague:T2

/etc/shadow     (hashes only, chmod 000)
```

## Federation

```
/etc/peers      known nodes
/etc/endpoints  route → target mappings

curl -u ranger:token node-a:3005/home/work/read         ← read local
curl -u ranger:token node-a:3005/proxy?url=node-b/read  ← read remote

Each node is a full Linux. Tailscale connects them.
```

## Philosophy

```
elastik started as 3,940 lines designed to restrict AI.
It was carved down to 300 lines that serve AI.
Then to 80 lines with no database.
Then it became Unix.

Nobody designed this mapping. It emerged.
Every system, given enough time, converges to the same shape.
That shape is Unix.

The emptiness is the product.

埏埴以为器，当其无，有器之用。
You shape clay into a vessel. It's the emptiness inside that makes it useful.
```

## One line

```
you have a Linux machine whose interface is curl.
```

🗿
