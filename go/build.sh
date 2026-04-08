#!/usr/bin/env bash
# Build elastik Go native server. Output: ../elastik (or .exe on Windows)
set -e
cd "$(dirname "$0")"
OUT="../elastik"
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) OUT="../elastik.exe";; esac
echo "Building $OUT..."
go build -o "$OUT" ./native
echo "OK  -> $OUT"
ls -lh "$OUT"
