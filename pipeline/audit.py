"""FrictionDeck v4 — Audit Layer

Append-only HMAC-SHA256 hash-chain ledger.
The black box. Not a firewall. A flight recorder.
"""

import hashlib
import hmac as _hmac
import json
import logging
import os
import sqlite3
from datetime import datetime, UTC
from pathlib import Path
from typing import Any
from uuid import uuid4

from pipeline.constants import EventType

logger = logging.getLogger("frictiondeck.audit")

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)

AUDIT_DB_DIR = os.environ.get(
    "FRICTIONDECK_DB_DIR", os.path.join(_PROJECT_ROOT, "data"),
)
AUDIT_DB_PATH = os.path.join(AUDIT_DB_DIR, "audit.db")

_conn: sqlite3.Connection | None = None


# ── Connection ───────────────────────────────────────────────────────────────


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(AUDIT_DB_DIR, exist_ok=True)
        _conn = sqlite3.connect(AUDIT_DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=FULL")
    return _conn


# ── Schema ───────────────────────────────────────────────────────────────────


def init_audit_db() -> None:
    conn = _get_conn()
    logger.info("init_audit_db  path=%s  exists=%s", AUDIT_DB_PATH, os.path.exists(AUDIT_DB_PATH))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id    TEXT NOT NULL UNIQUE,
            event_type  TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            actor       TEXT NOT NULL DEFAULT 'system',
            pathway     TEXT,
            payload     TEXT NOT NULL DEFAULT '{}',
            environment TEXT NOT NULL DEFAULT '{}',
            prev_hash   TEXT NOT NULL,
            event_hash  TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_audit_type   ON audit_events(event_type);
        CREATE INDEX IF NOT EXISTS idx_audit_actor   ON audit_events(actor);
        CREATE INDEX IF NOT EXISTS idx_audit_pathway ON audit_events(pathway);
    """)
    conn.commit()


# ── Environment snapshot ─────────────────────────────────────────────────────


def _collect_environment() -> str:
    """Collect runtime environment snapshot."""
    from pipeline.config import VERSION

    env: dict[str, Any] = {
        "frictiondeck_version": VERSION,
    }
    return json.dumps(env, ensure_ascii=False, sort_keys=True)


# ── Hash computation ─────────────────────────────────────────────────────────


def _compute_hash(event_id: str, event_type: str, timestamp: str,
                  prev_hash: str, environment: str, payload: str,
                  *, key: str) -> str:
    """Compute HMAC-SHA256 hash for an audit event."""
    canonical = f"{event_id}|{event_type}|{timestamp}|{prev_hash}|{environment}|{payload}"
    return _hmac.new(key.encode(), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


# ── Core logging ─────────────────────────────────────────────────────────────


def log_event(
    event_type: str,
    *,
    actor: str = "system",
    pathway: str | None = None,
    payload: dict[str, Any] | None = None,
) -> str:
    """Append an audit event to the hash chain.

    Uses BEGIN IMMEDIATE for atomic prev_hash read + insert.
    Returns the event_id (UUID hex).

    actor:   "ai", "user", "system"
    pathway: "mcp", "gui", "api", None
    """
    conn = _get_conn()
    event_id = uuid4().hex
    ts = datetime.now(UTC).isoformat()
    payload_json = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
    env_json = _collect_environment()

    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT event_hash FROM audit_events ORDER BY id DESC LIMIT 1",
        ).fetchone()
        prev_hash = row["event_hash"] if row else "GENESIS"

        from pipeline.config import AUDIT_HMAC_KEY
        event_hash = _compute_hash(
            event_id, event_type, ts, prev_hash, env_json, payload_json,
            key=AUDIT_HMAC_KEY,
        )

        conn.execute(
            "INSERT INTO audit_events "
            "(event_id, event_type, timestamp, actor, pathway, "
            " payload, environment, prev_hash, event_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, event_type, ts, actor, pathway,
             payload_json, env_json, prev_hash, event_hash),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return event_id


# ── Query functions ──────────────────────────────────────────────────────────


def get_audit_log(
    limit: int = 50,
    offset: int = 0,
    event_type: str | None = None,
    actor: str | None = None,
    pathway: str | None = None,
) -> list[dict]:
    conn = _get_conn()
    clauses: list[str] = []
    params: list[Any] = []

    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if actor:
        clauses.append("actor = ?")
        params.append(actor)
    if pathway:
        clauses.append("pathway = ?")
        params.append(pathway)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        f"SELECT * FROM audit_events{where} "
        f"ORDER BY id DESC LIMIT ? OFFSET ?"
    )
    params.extend([limit, offset])

    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ── Chain verification ───────────────────────────────────────────────────────


def _break_info(event: dict, index: int, expected: str) -> dict:
    """Build a chain-break info dict."""
    return {
        "event_index": index,
        "expected": expected,
        "got": event.get("prev_hash") or event.get("event_hash", "")[:16],
        "event_type": event["event_type"],
        "created_at": event["timestamp"],
    }


def _fetch_events(limit: int) -> list[dict]:
    """Fetch audit events for verification."""
    conn = _get_conn()
    if limit > 0:
        rows = conn.execute(
            "SELECT * FROM audit_events ORDER BY id ASC "
            "LIMIT ? OFFSET (SELECT MAX(0, COUNT(*) - ?) FROM audit_events)",
            (limit, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM audit_events ORDER BY id ASC",
        ).fetchall()
    return [dict(r) for r in rows]


def verify_chain(limit: int = 0) -> dict:
    """Verify hash chain integrity."""
    from pipeline.config import AUDIT_HMAC_KEY

    base: dict = {
        "valid": True, "degraded": False, "total_events": 0,
        "verified_events": 0, "unverifiable_events": 0,
        "anomalies": 0, "first_break": None,
        "verified_at": datetime.now(UTC).isoformat(),
    }

    events = _fetch_events(limit)
    if not events:
        return base

    verified = tampered = 0
    for i, event in enumerate(events):
        # Chain linkage check
        if i == 0 and event["id"] == 1 and event["prev_hash"] != "GENESIS":
            base.update(valid=False, total_events=len(events), anomalies=1,
                        first_break=_break_info(event, 1, "GENESIS"))
            return base
        if i > 0 and event["prev_hash"] != events[i - 1]["event_hash"]:
            base.update(valid=False, total_events=len(events),
                        verified_events=verified, anomalies=1,
                        first_break=_break_info(event, i + 1, events[i - 1]["event_hash"]))
            return base

        # Per-event HMAC check
        expected = _compute_hash(
            event["event_id"], event["event_type"], event["timestamp"],
            event["prev_hash"], event["environment"], event["payload"],
            key=AUDIT_HMAC_KEY,
        )
        if event["event_hash"] == expected:
            verified += 1
        else:
            tampered += 1
            if not base["first_break"]:
                info = _break_info(event, i + 1, expected[:16] + "…")
                info["reason"] = "tampered"
                base["first_break"] = info

    base["total_events"] = len(events)
    base["verified_events"] = verified
    if tampered > 0:
        base.update(valid=False, degraded=True, anomalies=tampered)
    return base


# ── Cleanup ──────────────────────────────────────────────────────────────────


def close_audit() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
