"""Background queue processor — runs inside the FastAPI event loop."""

import asyncio
import logging
import socket
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from db.session import CelerySessionLocal
from models import Anomaly, Case, Clause, Document
from case_queue.queue_service import (
    OpType,
    complete_op,
    process_next,
)

logger = logging.getLogger(__name__)

_poll_interval = 2  # seconds between queue checks
_max_retries = 3


def _is_connection_error(exc: Exception) -> bool:
    """Check if an exception is a DB connection/DNS error worth retrying."""
    if isinstance(exc, (socket.gaierror, OSError, ConnectionError)):
        return True
    if isinstance(exc, OperationalError) and exc.orig:
        return isinstance(exc.orig, (socket.gaierror, OSError, ConnectionError))
    return False


async def _execute_create_case(payload: dict[str, Any], firm_id: str) -> dict:
    """Create a case in the database."""
    async with CelerySessionLocal() as session:
        title = payload["title"].strip()
        country = payload.get("country")
        existing = await session.execute(
            select(Case).where(Case.firm_id == uuid.UUID(firm_id), Case.title == title)
        )
        if existing.scalar_one_or_none():
            raise ValueError("a case with this title already exists")
        case = Case(firm_id=uuid.UUID(firm_id), title=title, country=country)
        session.add(case)
        await session.commit()
        logger.info("created case %s (title=%s)", case.id, title)
        return {"id": str(case.id), "title": case.title}


async def _execute_delete_case(payload: dict[str, Any], firm_id: str) -> dict:
    """Delete a case and all its documents/clauses/anomalies."""
    async with CelerySessionLocal() as session:
        case_id = uuid.UUID(payload["case_id"])
        case = await session.get(Case, case_id)
        if case is None:
            raise ValueError("case not found")
        if str(case.firm_id) != str(firm_id):
            raise ValueError("case not found in this firm")

        doc_result = await session.execute(
            select(Document.id).where(Document.case_id == case_id)
        )
        doc_ids = [row[0] for row in doc_result.all()]

        if doc_ids:
            clause_result = await session.execute(
                select(Clause.id).where(Clause.document_id.in_(doc_ids))
            )
            clause_ids = [row[0] for row in clause_result.all()]
            if clause_ids:
                await session.execute(delete(Anomaly).where(Anomaly.clause_id.in_(clause_ids)))
                await session.execute(delete(Clause).where(Clause.document_id.in_(doc_ids)))
            await session.execute(delete(Document).where(Document.id.in_(doc_ids)))

        await session.execute(delete(Case).where(Case.id == case_id))
        await session.commit()
        logger.info("deleted case %s with %d documents", payload["case_id"], len(doc_ids))
        return {"deleted": payload["case_id"], "documents_deleted": len(doc_ids)}


async def process_one_operation() -> bool:
    """Process one queued operation with retry on DNS/connection errors."""
    op = await asyncio.to_thread(process_next)
    if op is None:
        return False

    op_id = op["id"]
    op_type = op["type"]
    payload = op.get("payload", {})
    firm_id = op.get("firm_id", "")

    logger.info("processing %s (id=%s)", op_type, op_id)

    last_err = None
    for attempt in range(_max_retries):
        try:
            if op_type == OpType.CREATE:
                result = await _execute_create_case(payload, firm_id)
            elif op_type == OpType.DELETE:
                result = await _execute_delete_case(payload, firm_id)
            else:
                raise ValueError(f"unknown operation type: {op_type}")

            await asyncio.to_thread(complete_op, op_id, result=result)
            logger.info("completed %s (id=%s): %s", op_type, op_id, result)
            return True

        except Exception as exc:
            last_err = exc
            if _is_connection_error(exc) and attempt < _max_retries - 1:
                logger.warning("DB connection error on attempt %d/%d for %s (id=%s): %s",
                              attempt + 1, _max_retries, op_type, op_id, exc)
                await asyncio.sleep(1.0 * (attempt + 1))
            else:
                logger.error("failed %s (id=%s): %s", op_type, op_id, exc, exc_info=True)
                await asyncio.to_thread(complete_op, op_id, error=str(exc))
                return True

    logger.error("failed %s (id=%s) after %d retries: %s", op_type, op_id, _max_retries, last_err)
    await asyncio.to_thread(complete_op, op_id, error=f"connection failed after {_max_retries} retries: {last_err}")
    return True


async def queue_processor_loop():
    """Background loop that continuously processes the queue."""
    logger.info("queue processor started (poll=%ss)", _poll_interval)
    while True:
        try:
            processed = await process_one_operation()
            if not processed:
                await asyncio.sleep(_poll_interval)
        except asyncio.CancelledError:
            logger.info("queue processor stopped")
            break
        except Exception:
            logger.exception("unexpected error in queue processor")
            await asyncio.sleep(_poll_interval)
