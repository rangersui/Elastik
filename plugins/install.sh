#!/bin/sh
# plugins/install.sh — install + activate one elastik plugin.
#
# Usage:
#   ./plugins/install.sh <plugin-name>
#   ELASTIK_APPROVE_TOKEN=... ./plugins/install.sh semantic
#
# Env (all optional, reasonable defaults for a local dev box):
#   ELASTIK_HOST            default http://localhost:3005
#   ELASTIK_APPROVE_TOKEN   required for non-localhost OR when the
#                           server is configured with a token
#   ELASTIK_TOKEN           fallback if APPROVE isn't set
#
# What it does:
#   1. PUT plugins/<name>.py  ->  /lib/<name>          (upload source)
#   2. PUT "active"           ->  /lib/<name>/state    (activate)
#
# Not done here (config is separate from install):
#   - /etc/gpu.conf            (gpu plugin needs this; write it yourself)
#   - any plugin-specific seeds
#
# Idempotent: re-running overwrites the source + re-activates. Server
# hot-swaps the plugin; no restart needed.

set -eu

PLUGIN="${1:-}"
HOST="${ELASTIK_HOST:-http://localhost:3005}"
TOKEN="${ELASTIK_APPROVE_TOKEN:-${ELASTIK_TOKEN:-}}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cyan() { printf '\033[36m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
red() { printf '\033[31m%s\033[0m\n' "$*" >&2; }

if [ -z "$PLUGIN" ]; then
    red "usage: $0 <plugin-name>"
    echo "" >&2
    echo "available plugins:" >&2
    for p in "$SCRIPT_DIR"/*.py; do
        name="$(basename "$p" .py)"
        case "$name" in
            __init__) continue ;;
        esac
        echo "  $name" >&2
    done
    exit 2
fi

SRC="$SCRIPT_DIR/${PLUGIN}.py"
if [ ! -f "$SRC" ]; then
    red "error: $SRC not found"
    red "(plugin name must match a .py file in plugins/)"
    exit 2
fi

cyan "Installing '$PLUGIN' -> $HOST"
echo "  source: $SRC"
if [ -n "$TOKEN" ]; then
    echo "  auth:   Bearer (token set)"
else
    echo "  auth:   (no token — works only on localhost with no server token configured)"
fi
echo ""

# Shared curl flags:
#   -f   fail with non-zero on HTTP 4xx/5xx (so rc != 0 catches
#        403/500/etc., not just connect failures). Without -f, curl
#        exits 0 on a 500 and the script would print "installed +
#        activated" after a server refusal.
#   -sS  silent progress bar, but still emit error messages.
#   -w   trailing line with the HTTP status so the user can see what
#        came back even on success.
#
# Note: we deliberately DO NOT use ${TOKEN:+-H "Authorization: Bearer $TOKEN"}
# here. Under /bin/sh that parameter expansion happens unquoted, so
# "Authorization: Bearer $TOKEN" splits on whitespace and curl sees
# multiple args instead of one -H. Branch explicitly instead.

# ── 1. upload source ──────────────────────────────────────────
echo "  1/2  PUT $SRC -> $HOST/lib/$PLUGIN"
set +e
if [ -n "$TOKEN" ]; then
    curl -fsS -X PUT "$HOST/lib/$PLUGIN" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: text/x-python" \
        --data-binary "@$SRC" \
        -w "\n       -> HTTP %{http_code}\n"
else
    curl -fsS -X PUT "$HOST/lib/$PLUGIN" \
        -H "Content-Type: text/x-python" \
        --data-binary "@$SRC" \
        -w "\n       -> HTTP %{http_code}\n"
fi
rc=$?
set -e
if [ $rc -ne 0 ]; then
    red "upload failed (curl exit $rc)."
    red "  - connection error? check the server is up at $HOST"
    red "  - HTTP 4xx/5xx?    check ELASTIK_APPROVE_TOKEN and server logs"
    exit 1
fi

# ── 2. activate ──────────────────────────────────────────────
echo ""
echo "  2/2  PUT active -> $HOST/lib/$PLUGIN/state"
set +e
if [ -n "$TOKEN" ]; then
    curl -fsS -X PUT "$HOST/lib/$PLUGIN/state" \
        -H "Authorization: Bearer $TOKEN" \
        -d "active" \
        -w "\n       -> HTTP %{http_code}\n"
else
    curl -fsS -X PUT "$HOST/lib/$PLUGIN/state" \
        -d "active" \
        -w "\n       -> HTTP %{http_code}\n"
fi
rc=$?
set -e
if [ $rc -ne 0 ]; then
    red "activation failed (curl exit $rc). Source was uploaded but"
    red "the plugin is still in 'pending' state. Retry with:"
    red "  curl -X PUT $HOST/lib/$PLUGIN/state \\"
    red "       -H \"Authorization: Bearer \$ELASTIK_APPROVE_TOKEN\" \\"
    red "       -d active"
    exit 1
fi

echo ""
green "installed + activated: $PLUGIN"
echo ""
echo "verify routes registered:"
echo "  curl $HOST/lib/"
echo ""
case "$PLUGIN" in
    semantic)
        cyan "semantic depends on /dev/gpu. If you haven't:"
        echo "  $0 gpu"
        echo "  curl -X PUT $HOST/etc/gpu.conf \\"
        echo "       ${TOKEN:+-H \"Authorization: Bearer \$ELASTIK_APPROVE_TOKEN\"} \\"
        echo "       -d 'ollama://127.0.0.1:11434'"
        ;;
    gpu)
        cyan "/dev/gpu needs a backend in /etc/gpu.conf. E.g.:"
        echo "  curl -X PUT $HOST/etc/gpu.conf \\"
        echo "       ${TOKEN:+-H \"Authorization: Bearer \$ELASTIK_APPROVE_TOKEN\"} \\"
        echo "       -d 'ollama://127.0.0.1:11434'"
        ;;
esac
