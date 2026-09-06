"""Case CRUD queue service — sequential processing with Redis list backend."""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import redis

from core.config import settings

logger = logging.getLogger(__name__)

_redis = redis.from_url(settings.redis_url, decode_responses=True)

QUEUE_KEY = "queue:case_ops"
RESULTS_PREFIX = "queue:result:"
LOCK_KEY = "queue:lock"
PROCESSING_KEY = "queue:processing"

TTL_SECONDS = 3600  # results expire after 1 hour


class OpType(str, Enum):
    CREATE = "create_case"
    DELETE = "delete_case"


class OpStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


def enqueue(operation: dict[str, Any]) -> dict[str, Any]:
    """Add an operation to the queue. Returns the operation with its ID and status."""
    op_id = str(uuid.uuid4())
    op = {
        "id": op_id,
        "type": operation["type"],
        "payload": operation.get("payload", {}),
        "firm_id": operation.get("firm_id"),
        "status": OpStatus.QUEUED,
        "queued_at": datetime.now(UTC).isoformat(),
        "result": None,
        "error": None,
    }
    _redis.rpush(QUEUE_KEY, json.dumps(op))
    _save_result(op_id, op)
    logger.info("enqueued %s (id=%s)", op["type"], op_id)
    return op


def get_status(op_id: str) -> dict[str, Any] | None:
    """Get the status of an operation by ID."""
    raw = _redis.get(f"{RESULTS_PREFIX}{op_id}")
    if raw:
        return json.loads(raw)
    return None


def get_queue_snapshot(limit: int = 20) -> list[dict[str, Any]]:
    """Return the current queue (up to limit items) + the currently processing item."""
    items = _redis.lrange(QUEUE_KEY, 0, limit - 1)
    result = []
    for raw in items:
        op = json.loads(raw)
        result.append(op)

    # Prepend currently processing item if not already in the list
    proc_raw = _redis.get(PROCESSING_KEY)
    if proc_raw:
        proc = json.loads(proc_raw)
        if not result or result[0].get("id") != proc.get("id"):
            result.insert(0, proc)
    return result


def cancel_op(op_id: str) -> bool:
    """Remove a queued operation (only works if still queued, not yet processing)."""
    proc_raw = _redis.get(PROCESSING_KEY)
    if proc_raw:
        proc = json.loads(proc_raw)
        if proc["id"] == op_id:
            return False  # can't cancel in-progress

    items = _redis.lrange(QUEUE_KEY, 0, -1)
    for raw in items:
        op = json.loads(raw)
        if op["id"] == op_id:
            _redis.lrem(QUEUE_KEY, 1, raw)
            op["status"] = OpStatus.FAILED
            op["error"] = "cancelled by user"
            _save_result(op_id, op)
            logger.info("cancelled operation %s", op_id)
            return True
    return False


def process_next() -> dict[str, Any] | None:
    """Pop the next operation and return it. Returns None if queue is empty."""
    raw = _redis.lpop(QUEUE_KEY)
    if not raw:
        return None
    op = json.loads(raw)
    op["status"] = OpStatus.PROCESSING
    op["started_at"] = datetime.now(UTC).isoformat()
    _redis.set(PROCESSING_KEY, json.dumps(op))
    _save_result(op["id"], op)
    return op


def complete_op(op_id: str, result: Any = None, error: str | None = None) -> None:
    """Mark an operation as done or failed."""
    proc_raw = _redis.get(PROCESSING_KEY)
    if proc_raw:
        proc = json.loads(proc_raw)
        if proc["id"] == op_id:
            _redis.delete(PROCESSING_KEY)

    op = get_status(op_id) or {}
    if error:
        op["status"] = OpStatus.FAILED
        op["error"] = error
    else:
        op["status"] = OpStatus.DONE
        op["result"] = result
    op["completed_at"] = datetime.now(UTC).isoformat()
    _save_result(op_id, op)


def _save_result(op_id: str, op: dict) -> None:
    _redis.setex(f"{RESULTS_PREFIX}{op_id}", TTL_SECONDS, json.dumps(op))
