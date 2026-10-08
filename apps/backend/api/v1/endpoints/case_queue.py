import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.v1.deps import get_current_user
from models import User
from case_queue.queue_service import (
    OpType,
    cancel_op,
    enqueue,
    get_queue_snapshot,
    get_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queue", tags=["case-queue"])


class EnqueueCreateRequest(BaseModel):
    title: str
    country: str | None = None


class EnqueueDeleteRequest(BaseModel):
    case_id: str


@router.post("/cases", status_code=202)
async def enqueue_create_case(
    payload: EnqueueCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    if not payload.title.strip():
        raise HTTPException(status_code=422, detail="title cannot be empty")
    op = enqueue({
        "type": OpType.CREATE,
        "payload": {"title": payload.title, "country": payload.country},
        "firm_id": str(user.firm_id),
    })
    return {
        "operation_id": op["id"],
        "status": op["status"],
        "queue_position": len(get_queue_snapshot()),
    }


@router.post("/cases/delete", status_code=202)
async def enqueue_delete_case(
    payload: EnqueueDeleteRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    op = enqueue({
        "type": OpType.DELETE,
        "payload": {"case_id": payload.case_id},
        "firm_id": str(user.firm_id),
    })
    return {
        "operation_id": op["id"],
        "status": op["status"],
        "queue_position": len(get_queue_snapshot()),
    }


@router.get("/status/{operation_id}")
async def get_operation_status(
    operation_id: str,
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    op = get_status(operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail="operation not found")
    return {
        "operation_id": op["id"],
        "type": op["type"],
        "status": op["status"],
        "result": op.get("result"),
        "error": op.get("error"),
        "queued_at": op.get("queued_at"),
        "completed_at": op.get("completed_at"),
    }


@router.delete("/operations/{operation_id}")
async def cancel_operation(
    operation_id: str,
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    success = cancel_op(operation_id)
    if not success:
        raise HTTPException(status_code=404, detail="operation not found or already processing")
    return {"cancelled": operation_id}


@router.get("/snapshot")
async def queue_snapshot(
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    items = get_queue_snapshot(limit=20)
    return {
        "items": [
            {
                "operation_id": op["id"],
                "type": op["type"],
                "status": op["status"],
                "payload": op.get("payload"),
                "queued_at": op.get("queued_at"),
                "completed_at": op.get("completed_at"),
                "error": op.get("error"),
            }
            for op in items
        ]
    }
