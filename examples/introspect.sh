#!/usr/bin/env bash
# examples/introspect.sh — snapshot this machine into elastik worlds.
#
# PUTs several probes to /home/env/* so any later curl can replay
# what this environment looked like at snapshot time. Tuned for
# localhost single-user; supports $ELASTIK_URL and $ELASTIK_TOKEN.
#
# Note: `ps -eo comm` (command name only) is used by default to avoid
# persisting secrets passed via CLI. Swap to `ps aux` if you want full
# command lines (and accept that argv gets stored).
set -euo pipefail

URL="${ELASTIK_URL:-http://127.0.0.1:3005}"
CURL=(-fsS --connect-timeout 3 --max-time 5)
if [ -n "${ELASTIK_TOKEN:-}" ]; then
    CURL+=(-H "Authorization: Bearer $ELASTIK_TOKEN")
fi

write() {
    local name="$1" content="$2"
    if printf '%s' "$content" | curl "${CURL[@]}" -X PUT --data-binary @- \
         "$URL/home/env/$name" >/dev/null; then
        printf '  wrote /home/env/%-14s %dB\n' "$name" "${#content}"
    else
        printf '  FAIL  /home/env/%s (curl exit %d)\n' "$name" "$?" >&2
        return 1
    fi
}

# sed -n '1,Np' instead of head -N: head closes its pipe after N lines,
# which under `set -o pipefail` makes the upstream command (ps, pip, ...)
# exit non-zero on SIGPIPE and aborts the whole snapshot. sed drains the
# full stream and just prints the first N lines. `|| echo -` is the
# belt-and-braces fallback for when the tool itself is missing (e.g.
# `pip` on a stock macOS).
write os        "$(uname -a)"
write disk      "$(df -h 2>/dev/null || echo -)"
write memory    "$(free -h 2>/dev/null || vm_stat 2>/dev/null || echo -)"
write network   "$(ip addr 2>/dev/null || ifconfig 2>/dev/null || echo -)"
write dns       "$(cat /etc/resolv.conf 2>/dev/null || echo -)"
write processes "$(ps -eo user,pid,pcpu,pmem,comm 2>/dev/null | sed -n '1,50p' || echo -)"
write pip       "$(pip list 2>/dev/null | sed -n '1,30p' || echo -)"
write languages "$(
    echo "python: $(python3 --version 2>&1 || echo -)"
    echo "node:   $(node --version 2>&1 || echo -)"
    echo "go:     $(go version 2>&1 || echo -)"
    echo "rust:   $(rustc --version 2>&1 || echo -)"
)"
write connectivity "$(
    for h in google.com github.com pypi.org; do
        code=$(curl -sS -o /dev/null --connect-timeout 3 --max-time 5 \
                    -w '%{http_code}' "https://$h" 2>/dev/null || echo err)
        echo "$h: $code"
    done
)"

echo
echo "read back:"
echo "  curl $URL/home/env/                 # list"
echo "  curl $URL/home/env/processes?raw    # read content"
