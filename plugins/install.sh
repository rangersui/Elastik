#!/bin/sh
# plugins/install.sh - install + activate elastik plugins.
#
# Usage:
#   ./plugins/install.sh <plugin-name>
#   ./plugins/install.sh primitives
#   ./plugins/install.sh primitives --with-semantic
#   ELASTIK_APPROVE_TOKEN=... ./plugins/install.sh semantic
#
# Env (all optional, reasonable defaults for a local dev box):
#   ELASTIK_HOST            default http://localhost:3005
#   ELASTIK_APPROVE_TOKEN   preferred auth token for upload + activation
#   ELASTIK_TOKEN           fallback if APPROVE isn't set
#
# What it does:
#   1. PUT plugins/<name>.py  ->  /lib/<name>          (upload source)
#   2. PUT "active"           ->  /lib/<name>/state    (activate)
#
# Special target:
#   primitives               installs gpu + fstab + db + fanout
#   --with-semantic          add semantic after primitives
#
# Not done here (config is separate from install):
#   - /etc/gpu.conf
#   - /etc/fstab
#   - any plugin-specific seeds
#
# Idempotent: re-running overwrites the source + re-activates. Server
# hot-swaps the plugin; no restart needed.

set -eu

PLUGIN="${1:-}"
WITH_SEMANTIC=0
HOST="${ELASTIK_HOST:-http://localhost:3005}"
TOKEN="${ELASTIK_APPROVE_TOKEN:-${ELASTIK_TOKEN:-}}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cyan() { printf '\033[36m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
red() { printf '\033[31m%s\033[0m\n' "$*" >&2; }

show_usage() {
    red "usage: $0 <plugin-name>"
    red "       $0 primitives [--with-semantic]"
    echo "" >&2
    echo "available plugins:" >&2
    for p in "$SCRIPT_DIR"/*.py; do
        name="$(basename "$p" .py)"
        case "$name" in
            __init__) continue ;;
        esac
        echo "  $name" >&2
    done
    echo "" >&2
    echo "special targets:" >&2
    echo "  primitives        gpu + fstab + db + fanout" >&2
    echo "  --with-semantic   add semantic after primitives" >&2
}

for arg in "$@"; do
    case "$arg" in
        --with-semantic) WITH_SEMANTIC=1 ;;
    esac
done

if [ -z "$PLUGIN" ]; then
    show_usage
    exit 2
fi

# Shared curl flags:
#   -f   fail with non-zero on HTTP 4xx/5xx.
#   -sS  hide progress, keep error messages.
#   -w   show the status code even on success.
#
# We branch explicitly for the auth header instead of relying on
# parameter expansion tricks so /bin/sh never splits the header arg.

show_post_install_hint() {
    case "$1" in
        semantic)
            cyan "semantic depends on /dev/gpu. If you haven't:"
            echo "  $0 gpu"
            if [ -n "$TOKEN" ]; then
                echo "  curl -X PUT $HOST/etc/gpu.conf \\"
                echo "       -H \"Authorization: Bearer \$ELASTIK_APPROVE_TOKEN\" \\"
                echo "       -d 'ollama://127.0.0.1:11434'"
            else
                echo "  curl -X PUT $HOST/etc/gpu.conf -d 'ollama://127.0.0.1:11434'"
            fi
            ;;
        gpu)
            cyan "/dev/gpu needs a backend in /etc/gpu.conf. E.g.:"
            if [ -n "$TOKEN" ]; then
                echo "  curl -X PUT $HOST/etc/gpu.conf \\"
                echo "       -H \"Authorization: Bearer \$ELASTIK_APPROVE_TOKEN\" \\"
                echo "       -d 'ollama://127.0.0.1:11434'"
            else
                echo "  curl -X PUT $HOST/etc/gpu.conf -d 'ollama://127.0.0.1:11434'"
            fi
            ;;
    esac
}

install_one() {
    name="$1"
    src="$SCRIPT_DIR/${name}.py"

    if [ ! -f "$src" ]; then
        red "error: $src not found"
        red "(plugin name must match a .py file in plugins/)"
        exit 2
    fi

    cyan "Installing '$name' -> $HOST"
    echo "  source: $src"
    if [ -n "$TOKEN" ]; then
        echo "  auth:   Bearer (token set)"
    else
        echo "  auth:   (no token - works only on localhost with no server token configured)"
    fi
    echo ""

    echo "  1/2  PUT $src -> $HOST/lib/$name"
    set +e
    if [ -n "$TOKEN" ]; then
        curl -fsS -X PUT "$HOST/lib/$name" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: text/x-python" \
            --data-binary "@$src" \
            -w "\n       -> HTTP %{http_code}\n"
    else
        curl -fsS -X PUT "$HOST/lib/$name" \
            -H "Content-Type: text/x-python" \
            --data-binary "@$src" \
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

    echo ""
    echo "  2/2  PUT active -> $HOST/lib/$name/state"
    set +e
    if [ -n "$TOKEN" ]; then
        curl -fsS -X PUT "$HOST/lib/$name/state" \
            -H "Authorization: Bearer $TOKEN" \
            -d "active" \
            -w "\n       -> HTTP %{http_code}\n"
    else
        curl -fsS -X PUT "$HOST/lib/$name/state" \
            -d "active" \
            -w "\n       -> HTTP %{http_code}\n"
    fi
    rc=$?
    set -e
    if [ $rc -ne 0 ]; then
        red "activation failed (curl exit $rc). Source was uploaded but"
        red "the plugin is still in 'pending' state. Retry with:"
        red "  curl -X PUT $HOST/lib/$name/state \\"
        red "       -H \"Authorization: Bearer \$ELASTIK_APPROVE_TOKEN\" \\"
        red "       -d active"
        exit 1
    fi

    echo ""
    green "installed + activated: $name"
    echo ""
    show_post_install_hint "$name"
    case "$name" in
        semantic|gpu) echo "" ;;
    esac
}

if [ "$PLUGIN" = "primitives" ]; then
    targets="gpu fstab db fanout"
    [ "$WITH_SEMANTIC" -eq 1 ] && targets="$targets semantic"

    cyan "Installing primitive set -> $HOST"
    echo "  plugins: $targets"
    if [ -n "$TOKEN" ]; then
        echo "  auth:    Bearer (token set)"
    else
        echo "  auth:    (no token - works only on localhost with no server token configured)"
    fi
    echo ""

    for name in $targets; do
        install_one "$name"
    done

    green "primitive set installed: $targets"
    echo ""
    echo "verify routes registered:"
    echo "  curl $HOST/lib/"
    exit 0
fi

if [ "$WITH_SEMANTIC" -eq 1 ]; then
    red "--with-semantic is only valid with the 'primitives' target"
    exit 2
fi

install_one "$PLUGIN"
echo "verify routes registered:"
echo "  curl $HOST/lib/"
