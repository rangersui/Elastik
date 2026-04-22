# plugins/

This directory is for **server primitives** that are installed as
`/lib/<name>` worlds.

A plugin belongs here when it changes elastik's behavior from the server side:

- adds routes
- adds device surfaces
- adds replication or cloning capabilities
- adds negotiated response logic
- becomes part of the machine's primitive vocabulary

Rule of thumb:

- `plugins/` = "server behavior"
- `clients/` = "external consumer"

## Current primitives

| File | Route(s) | Role |
|---|---|---|
| `example.py` | `/example` | smallest Tier 1 specimen; template for a route plugin |
| `reality.py` | `/__reality__`, `/self` | self-replication — data tar.gz + source tar.gz |
| `gpu.py` | `/dev/gpu` | blind AI device; backend from `/etc/gpu.conf` |
| `fstab.py` | `/mnt/*` | blind mount of local directories; mount table in `/etc/fstab` |
| `db.py` | `/dev/db` | read-only SQL over worlds or fstab-mounted SQLite files |
| `fanout.py` | `/dev/fanout` | broadcast one write to N worlds; target list in `/etc/fanout.conf` |
| `semantic.py` | `/shaped/*` | Accept/User-Agent driven shape renderer; delegates to `/dev/gpu` |

`gpu` / `fstab` / `db` / `fanout` form a **machine-primitives set** —
blind device, blind mount, blind query, blind broadcast. Each has a
config world under `/etc/<plugin>` or `/etc/<plugin>.conf`; runtime
behaviour swaps by `PUT /etc/...` without a plugin reload. `semantic.py`
is a higher-layer plugin that composes on top of `/dev/gpu`.

## Install model

Plugins are not auto-loaded from the repo checkout. They are staged into
`/lib/<name>` and then activated. The `install.sh` / `install.ps1`
helpers wrap the two-PUT dance:

```bash
# One plugin, one command:
export ELASTIK_TOKEN=your-t2-token
export ELASTIK_APPROVE_TOKEN=your-t3-token
./plugins/install.sh gpu
./plugins/install.sh fstab
./plugins/install.sh semantic
```

```powershell
# PowerShell
$env:ELASTIK_TOKEN="your-t2-token"
$env:ELASTIK_APPROVE_TOKEN="your-t3-token"
.\plugins\install.ps1 gpu
.\plugins\install.ps1 fstab
.\plugins\install.ps1 semantic
```

If you do not want to set env vars first, PowerShell can also pass the
token explicitly:

```powershell
.\plugins\install.ps1 gpu -Token "your-t3-token"
```

The raw HTTP form (what the helpers run for you):

```bash
curl -X PUT http://localhost:3005/lib/example \
  -H "Authorization: Bearer $ELASTIK_TOKEN" \
  --data-binary @plugins/example.py

curl -X PUT http://localhost:3005/lib/example/state \
  -H "Authorization: Bearer $ELASTIK_APPROVE_TOKEN" \
  --data-binary "active"
```

Same pattern for every plugin in the table above.

## What does NOT belong here

Do not put these in `plugins/`:

- desktop app wrappers
- Office workbooks/documents/decks
- shell convenience clients
- bots that merely call elastik over HTTP
- dashboards that render existing routes without extending the server

Those belong in [`clients/`](../clients/README.md).
