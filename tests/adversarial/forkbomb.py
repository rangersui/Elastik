"""Adversarial: fork bomb — spawns child processes to test containment.

Proves: Go's context.WithTimeout kills the parent, and child processes
don't escape to consume system resources indefinitely.

NOT a real fork bomb (:(){ :|:& };:) — we spawn a controlled number
of children that sleep, then check if Go kills the parent and whether
children get cleaned up.
"""
import sys, json, os, subprocess, time

if len(sys.argv) > 1 and sys.argv[1] == "--routes":
    print(json.dumps(["/forkbomb"]))
    sys.exit(0)

if len(sys.argv) > 1 and sys.argv[1] == "--child":
    # Child process: sleep forever (Go should kill us via process group)
    time.sleep(300)
    sys.exit(0)

d = json.loads(sys.stdin.readline())

# Spawn 5 child processes that sleep forever
children = []
for _ in range(5):
    p = subprocess.Popen(
        [sys.executable, __file__, "--child"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    children.append(p.pid)

# Now sleep forever ourselves — Go must kill us via timeout
# Report child PIDs so the test can verify they're cleaned up
sys.stdout.write(json.dumps({"status": 200, "body": json.dumps({"parent": os.getpid(), "children": children})}))
sys.stdout.flush()
time.sleep(300)
