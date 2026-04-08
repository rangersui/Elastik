"""Adversarial: slow drip — outputs bytes one at a time with long sleeps.

Proves: Go's pluginTimeout (30s) kills slow plugins with 504.
A real proxy/buffer penetration test would need SSE, but in CGI mode
this tests the timeout mechanism itself.
"""
import sys, json, time

if len(sys.argv) > 1 and sys.argv[1] == "--routes":
    print(json.dumps(["/slowdrip"]))
    sys.exit(0)

d = json.loads(sys.stdin.readline())
sys.stdout.write('{"status": 200, "body": "')
sys.stdout.flush()
# Drip one dot every 5 seconds — 10 dots = 50s, exceeds 30s timeout
for i in range(10):
    sys.stdout.write(".")
    sys.stdout.flush()
    time.sleep(5)
sys.stdout.write('"}')
sys.stdout.flush()
