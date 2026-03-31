"""Backup/restore elastik data. Zero token cost.

Usage:
  python scripts/backup.py backup              # backup all worlds
  python scripts/backup.py backup --name xxx   # backup one world
  python scripts/backup.py restore 20260331    # restore from backup
  python scripts/backup.py list                # list all backups
"""
import shutil, sqlite3, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BACKUPS = ROOT / "backups"
MAX_BACKUPS = 7


def backup(name=None):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUPS / ts
    dest.mkdir(parents=True)

    if name:
        worlds = [DATA / name]
    else:
        worlds = sorted(d for d in DATA.iterdir()
                        if d.is_dir() and (d / "universe.db").exists())

    for d in worlds:
        db_path = d / "universe.db"
        if not db_path.exists():
            print(f"  skipped: {d.name} (no db)")
            continue
        try:
            c = sqlite3.connect(str(db_path))
            c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            c.close()
        except Exception:
            pass
        shutil.copy2(db_path, dest / f"{d.name}.db")

    # Backup env files
    for env_name in (".env", "_env", ".env.local"):
        env_file = ROOT / env_name
        if env_file.exists():
            shutil.copy2(env_file, dest / env_name.replace(".", "dot-"))
            break

    size_kb = sum(f.stat().st_size for f in dest.iterdir()) / 1024
    print(f"  backed up {len(worlds)} worlds -> {ts} ({size_kb:.0f} KB)")

    # Retention
    all_backups = sorted(d for d in BACKUPS.iterdir() if d.is_dir())
    while len(all_backups) > MAX_BACKUPS:
        oldest = all_backups.pop(0)
        shutil.rmtree(oldest)
        print(f"  pruned: {oldest.name}")


def restore(ts):
    matches = sorted(d for d in BACKUPS.iterdir() if d.is_dir() and d.name.startswith(ts))
    if not matches:
        print(f"  backup '{ts}' not found")
        return
    src = matches[-1]
    count = 0
    for db_file in sorted(src.glob("*.db")):
        target_dir = DATA / db_file.stem
        target_dir.mkdir(parents=True, exist_ok=True)
        for ext in ("-shm", "-wal"):
            stale = target_dir / f"universe.db{ext}"
            try: stale.unlink(missing_ok=True)
            except OSError: pass
        shutil.copy2(db_file, target_dir / "universe.db")
        count += 1
    print(f"  restored {count} worlds from {src.name}")
    print(f"  restart server to apply")


def list_backups():
    if not BACKUPS.exists():
        print("  no backups")
        return
    for d in sorted(BACKUPS.iterdir()):
        if not d.is_dir():
            continue
        count = len(list(d.glob("*.db")))
        size_kb = sum(f.stat().st_size for f in d.iterdir()) / 1024
        print(f"  {d.name}  ({count} worlds, {size_kb:.0f} KB)")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("backup", "restore", "list"):
        print(__doc__)
        sys.exit(1)

    action = sys.argv[1]
    if action == "backup" and not DATA.exists():
        print("  no data directory")
        sys.exit(1)

    if action == "backup":
        name = None
        if "--name" in sys.argv:
            idx = sys.argv.index("--name")
            name = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        backup(name)
    elif action == "restore":
        if len(sys.argv) < 3:
            print("  usage: python scripts/backup.py restore <timestamp>")
            sys.exit(1)
        restore(sys.argv[2])
    elif action == "list":
        list_backups()
