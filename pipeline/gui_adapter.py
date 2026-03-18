"""FrictionDeck v4 — GUI Adapter (Human's hands)

All operations a human can perform through the GUI.
Physical isolation from mcp_adapter — zero intersection.
CI scans enforce: approve/lock/delete NEVER appear in mcp_adapter.

Operations only humans can do:
  approve_commit, reject_commit, lock_parameter, unlock_parameter
"""

import hashlib
import json
import logging
from datetime import datetime, UTC

from pipeline.constants import EventType, JudgmentState
from pipeline.stage import get_judgments, seal_judgments

logger = logging.getLogger("frictiondeck.gui_adapter")


# ═══════════════════════════════════════════════════════════════════════════
# Parameter operations (human only: lock/unlock)
# ═══════════════════════════════════════════════════════════════════════════


def lock_parameter(judgment_id: str, param_name: str) -> dict:
    """Lock a parameter. AI cannot modify locked parameters.

    Lock = human confirmation. "I've verified this value."
    """
    from pipeline.audit import log_event

    log_event(
        EventType.PARAM_LOCKED,
        actor="user",
        pathway="gui",
        payload={"judgment_id": judgment_id, "param_name": param_name},
    )
    return {"status": "locked", "judgment_id": judgment_id, "param_name": param_name}


def unlock_parameter(judgment_id: str, param_name: str) -> dict:
    """Unlock a parameter. AI can modify again."""
    from pipeline.audit import log_event

    log_event(
        EventType.PARAM_UNLOCKED,
        actor="user",
        pathway="gui",
        payload={"judgment_id": judgment_id, "param_name": param_name},
    )
    return {"status": "unlocked", "judgment_id": judgment_id, "param_name": param_name}


# ═══════════════════════════════════════════════════════════════════════════
# Commit operations (human only)
# ═══════════════════════════════════════════════════════════════════════════


def _generate_commit_id(proposal_id: str, engineer: str) -> str:
    """Deterministic commit ID from proposal + engineer + timestamp."""
    return hashlib.sha256(
        f"{proposal_id}|{engineer}|{datetime.now(UTC).isoformat()}".encode()
    ).hexdigest()[:16]


def approve_commit(
    proposal_id: str,
    engineer: str = "ranger",
) -> dict:
    """Approve a commit proposal. Direct seal + HMAC."""
    from pipeline.audit import log_event

    judgments = get_judgments(state=JudgmentState.VISCOUS)
    judgment_ids = [j["judgment_id"] for j in judgments]
    if not judgment_ids:
        return {"error": "No viscous judgments to commit."}

    commit_id = _generate_commit_id(proposal_id, engineer)
    seal_result = seal_judgments(judgment_ids, commit_id)

    log_event(
        EventType.COMMIT_APPROVED, actor="user", pathway="gui",
        payload={
            "commit_id": commit_id, "proposal_id": proposal_id,
            "judgment_ids": judgment_ids, "engineer": engineer,
            "sealed": seal_result["sealed"],
        },
    )

    logger.info("commit approved  id=%s  sealed=%d", commit_id, seal_result["sealed"])
    return {
        "commit_id": commit_id, "proposal_id": proposal_id,
        "sealed": seal_result["sealed"], "version": seal_result["version"],
        "status": "committed",
    }


def reject_commit(proposal_id: str, reason: str) -> dict:
    """Reject a commit proposal."""
    from pipeline.audit import log_event

    log_event(
        EventType.COMMIT_REJECTED,
        actor="user",
        pathway="gui",
        payload={"proposal_id": proposal_id, "reason": reason[:500]},
    )

    return {"proposal_id": proposal_id, "status": "rejected", "reason": reason}
