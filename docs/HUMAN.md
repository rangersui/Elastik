# elastik: the idiot's guide to your own Linux

Your system is a Linux box. It just runs on HTTP.

## Start

```bash
python server.py
```

Open http://localhost:3005. Done.

## Three things

```bash
curl localhost:3005/home/work              # read
curl -X PUT localhost:3005/home/work -d hi # write
curl localhost:3005/home/                  # list
```

GET reads. PUT writes. POST appends. DELETE deletes. Trailing `/` = ls.
Browser opens the same URL and sees a rendered page. curl gets JSON. Same address, two modes.

## Directory layout

Same as Linux.

```
/home/       your stuff. worlds. write freely.
/etc/        config. needs approve token (T3) to write.
/boot/       startup config. needs T3 to read. changes need restart.
/usr/lib/    skill docs, renderers. auto-synced at startup.
/var/log/    logs. health, sync results.
/proc/       system status. read-only.
/bin/        commands. all loaded plugin routes.
/dev/        devices. stone, fire, river, db.
/mnt/        local folders. configured via /etc/fstab.
/dav/        WebDAV. mount in Finder/Explorer.
```

## Permissions: three tiers

```
T1 (no token)      can read all public worlds
T2 (auth token)    can write /home/*
T3 (approve token) can write /etc/*, /usr/*, /var/*, /boot/*. can delete. can open browser.
```

Tokens live in `.env`:
```
ELASTIK_TOKEN=your-t2-password
ELASTIK_APPROVE_TOKEN=your-t3-password
```

curl with tokens:
```bash
# T2
curl -X PUT localhost:3005/home/work -H "Authorization: Bearer $TOKEN" -d "hello"

# T3
curl -X PUT localhost:3005/etc/myconfig \
  -H "Authorization: Basic $(echo -n ':$APPROVE' | base64)" -d "key=value"
```

## Mount local folders

This is where it gets violent. elastik can read your local filesystem — but only directories you explicitly whitelist.

```bash
# 1. Write fstab (needs T3 — this IS the permission)
curl -X PUT localhost:3005/etc/fstab \
  -H "Authorization: Basic $(echo -n ':$APPROVE' | base64)" \
  -d "C:/Users/you/Downloads  /mnt/downloads  ro
C:/Users/you/projects       /mnt/code       rw"

# 2. Use it
curl localhost:3005/mnt/downloads/           # ls directory
curl localhost:3005/mnt/downloads/file.txt   # read file
curl localhost:3005/mnt/code/               # ls another mount
```

`ro` = read-only. `rw` = read-write. Paths not in fstab → 404.
Edit fstab → takes effect on the next request. No restart.

How it works: there is no mount. No kernel. No FUSE. It reads the fstab world (a plain text string), parses each line, and does `os.path.join(local_path, subpath)` then `open()`. It's string concatenation. 80 lines of nginx `alias`.

## Query any SQLite database

This is the pipe that connects everything. `/dev/db` is a read-only SQL device.

```bash
# Query an elastik world's database
curl -X POST "localhost:3005/dev/db?world=work" \
  -H "Authorization: Bearer $TOKEN" \
  -d "SELECT version, ext FROM stage_meta"

# Query your BROWSER HISTORY (mount it first, then SQL it)
curl -X PUT localhost:3005/etc/fstab \
  -H "Authorization: Basic $(echo -n ':$APPROVE' | base64)" \
  -d "C:/Users/you/AppData/Local/BraveSoftware/Brave-Browser/User Data/Default  /mnt/brave  ro"

curl -X POST "localhost:3005/dev/db?file=brave/History" \
  -H "Authorization: Bearer $TOKEN" \
  -d "SELECT url, title FROM urls WHERE title LIKE '%github%' LIMIT 5"
```

Read that again. You just:
1. Wrote a line to `/etc/fstab` — mounted your browser profile
2. Used `/dev/db` — pointed it at the mounted path
3. Ran a SQL query against Chrome/Brave's History database
4. Got results. Local. Zero tokens. Zero cloud.

Google wants to send your entire history to their servers, embed it, semantic-search it, and charge you for the privilege. You did `LIKE '%github%'`.

Read-only. Two layers: keyword whitelist (SELECT only) + SQLite connection `mode=ro&immutable=1`. Can't write. Can't even lock the file — reads it while Brave is running.

## Browser remote control

```bash
# Open (needs T3)
curl -X POST "localhost:3005/opt/browser/open?url=https://example.com" \
  -H "Authorization: Basic $(echo -n ':$APPROVE' | base64)"

# See
curl localhost:3005/opt/browser/screenshot              # PNG base64
curl "localhost:3005/opt/browser/extract?s=h1"          # text of <h1> elements

# Act
curl -X POST "localhost:3005/opt/browser/click?x=200&y=300"
curl -X POST localhost:3005/opt/browser/type -d "hello"
curl -X POST localhost:3005/opt/browser/scroll?y=500
curl -X POST localhost:3005/opt/browser/back

# Close
curl -X POST localhost:3005/opt/browser/close
```

No eval. Cannot run arbitrary JS. Can see, read specific elements, click, type.
Launches incognito — no cookies, no logins, no sessions.

How it works: Chrome DevTools Protocol. A WebSocket to `localhost:9222`. The same thing Puppeteer/Playwright/Selenium call underneath, minus 50,000 lines of npm. The WebSocket client is 50 lines of stdlib Python. Detects Chrome, Brave, or Edge.

## WebDAV

```bash
# macOS
mount_webdav http://localhost:3005/dav /mnt/elastik

# Windows
net use Z: http://localhost:3005/dav

# Then browse in Finder / Explorer like a normal folder
```

DAV tree mirrors HTTP: `/dav/home/`, `/dav/etc/`, `/dav/boot/`.

## Useful commands

```bash
curl localhost:3005/proc/version          # version number
curl localhost:3005/proc/uptime           # seconds since boot
curl localhost:3005/proc/status           # pid, worlds, plugins
curl localhost:3005/bin                   # all available commands
curl localhost:3005/bin/cowsay?say=hello  # moo
curl localhost:3005/bin/grep?q=error      # full-text search all worlds
curl -X POST localhost:3005/flush         # flush the toilet (SSE test)
```

## Testing

```bash
# Full self-check (52 tests)
python tests/boot.py

# Or let elastik test itself
curl -s "localhost:3005/home/boot?raw" | python -X utf8 -
```

The second one: the test script lives inside elastik as a world. elastik serves the script to itself via HTTP, the script curls elastik's own routes, and reports. The compiler compiles itself.

## Pipes

curl output is plain text. Unix pipes just work.

```bash
curl localhost:3005/home/ | grep boot        # search world names
curl localhost:3005/home/ | wc -l            # count worlds
curl localhost:3005/bin | grep say            # find commands
curl localhost:3005/home/ | shuf | head -1    # random world
```

## The pipe that blew my mind

```bash
# Mount your Brave profile
curl -X PUT localhost:3005/etc/fstab -H "Authorization: Basic $AUTH" \
  -d "C:/Users/you/AppData/Local/BraveSoftware/...  /mnt/brave  ro"

# Query your browser history through elastik's SQL device
curl -X POST "localhost:3005/dev/db?file=brave/History" \
  -d "SELECT url FROM urls WHERE title LIKE '%pizza%'" \
  | head -5

# Take a screenshot of a live website through elastik's browser
curl -X POST "localhost:3005/opt/browser/open?url=https://github.com"
curl "localhost:3005/opt/browser/extract?s=h1"

# Write the result into an elastik world
curl "localhost:3005/opt/browser/extract?s=p" \
  | curl -X PUT localhost:3005/home/scraped -d @-

# Feed it to the SHA-256 oracle
curl localhost:3005/home/scraped | curl -X POST localhost:3005/bones -d @-
```

fstab → mount → /dev/db → SQL → pipe → /opt/browser → extract → pipe → PUT world → pipe → oracle.

Everything is curl. Everything is a pipe. Every output is another input.

## Remember

```
GET    = read (cat)
PUT    = write (echo >)
POST   = append (echo >>)
DELETE = delete (rm)
/      = list (ls)
```

That's it.
