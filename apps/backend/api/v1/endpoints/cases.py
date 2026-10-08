import base64
import io
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

import redis
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fpdf import FPDF
from pydantic import BaseModel
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.deps import get_current_user
from cache.llm_cache import _redis
from db.session import get_session_with_retry as get_session
from models import Anomaly, Case, Clause, Document, ReferenceChunk, ReferenceDocument, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["cases"])

_UNICODE_MAP = str.maketrans({
    "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2026": "...", "\u00a0": " ",
})


def _safe_text(text: str) -> str:
    return text.translate(_UNICODE_MAP).encode("latin-1", "replace").decode("latin-1")


class CaseCreateRequest(BaseModel):
    title: str
    country: str | None = None


def _encode_cursor(created_at: datetime, case_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(
        json.dumps([created_at.isoformat(), str(case_id)]).encode()
    ).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        created_at_iso, case_id = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(created_at_iso), uuid.UUID(case_id)
    except (ValueError, json.JSONDecodeError, uuid.UUIDError):
        raise HTTPException(status_code=400, detail="invalid cursor")
    return datetime.fromisoformat(created_at_iso), uuid.UUID(case_id)


@router.post("", status_code=201)
async def create_case(
    payload: CaseCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="title cannot be empty")
    existing = await session.execute(
        select(Case).where(Case.firm_id == user.firm_id, Case.title == title)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="a case with this title already exists")
    case = Case(firm_id=user.firm_id, title=title, country=payload.country)
    session.add(case)
    await session.commit()
    return {"id": str(case.id), "title": case.title}


@router.get("")
async def list_cases(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 20,
    cursor: str | None = None,
) -> dict[str, object]:
    query = (
        select(Case)
        .where(Case.firm_id == user.firm_id)
        .order_by(Case.created_at.desc(), Case.id)
    )
    if cursor:
        cursor_created_at, cursor_id = _decode_cursor(cursor)
        query = query.where(
            or_(
                Case.created_at < cursor_created_at,
                (Case.created_at == cursor_created_at) & (Case.id < cursor_id),
            )
        )
    query = query.limit(limit + 1)
    result = await session.execute(query)
    cases = result.scalars().all()
    has_more = len(cases) > limit
    items = cases[:limit]
    next_cursor = (
        _encode_cursor(items[-1].created_at, items[-1].id)
        if has_more and items
        else None
    )
    return {
        "items": [
            {
                "id": str(c.id),
                "title": c.title,
                "status": c.status,
                "country": c.country,
                "created_at": c.created_at.isoformat(),
            }
            for c in items
        ],
        "next_cursor": next_cursor,
    }


async def _get_owned_case(case_id: str, user: User, session: AsyncSession) -> Case:
    case = await session.get(Case, case_id)
    if case is None or case.firm_id != user.firm_id:
        raise HTTPException(status_code=404, detail="case not found")
    return case


@router.get("/{case_id}")
async def get_case(
    case_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str | None]:
    case = await _get_owned_case(case_id, user, session)
    return {"id": str(case.id), "title": case.title, "status": case.status, "country": case.country}


class CaseUpdateRequest(BaseModel):
    title: str | None = None
    status: str | None = None
    country: str | None = None


@router.patch("/{case_id}")
async def update_case(
    case_id: str,
    payload: CaseUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    case = await _get_owned_case(case_id, user, session)
    if payload.title is not None:
        case.title = payload.title
    if payload.status is not None:
        case.status = payload.status
    if payload.country is not None:
        case.country = payload.country
    await session.commit()
    return {"id": str(case.id), "title": case.title, "status": case.status, "country": case.country}


@router.delete("/{case_id}")
async def delete_case(
    case_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """
    Delete a case including all its documents and related data.
    """
    case = await _get_owned_case(case_id, user, session)
    case_uuid = case.id

    from services.reference_cache_service import get_reference_cache

    cache = get_reference_cache()
    if case_uuid in cache._cache:
        del cache._cache[case_uuid]
        del cache._filename_map[case_uuid]
        logger.info("cleared reference cache for case %s", case_uuid)
    doc_result = await session.execute(
        select(Document.id).where(Document.case_id == case_uuid)
    )
    doc_ids = [row[0] for row in doc_result.all()]
    deleted_keys = 0
    try:
        keys_to_delete = list(_redis.scan_iter("llm:*"))
        if keys_to_delete:
            pipe = _redis.pipeline()
            for key in keys_to_delete:
                pipe.delete(key)
            deleted_keys = sum(pipe.execute())
    except redis.RedisError:
        logger.warning("failed to clean redis cache")
    if doc_ids:
        clause_result = await session.execute(
            select(Clause.id).where(Clause.document_id.in_(doc_ids))
        )
        clause_ids = [row[0] for row in clause_result.all()]
        if clause_ids:
            await session.execute(
                delete(Anomaly).where(Anomaly.clause_id.in_(clause_ids))
            )
            await session.execute(
                delete(Clause).where(Clause.document_id.in_(doc_ids))
            )
        await session.execute(
            delete(Document).where(Document.id.in_(doc_ids))
        )
    await session.execute(
        delete(ReferenceChunk).where(
            ReferenceChunk.reference_document_id.in_(
                select(ReferenceDocument.id).where(ReferenceDocument.case_id == case_uuid)
            )
        )
    )
    await session.execute(
        delete(ReferenceDocument).where(ReferenceDocument.case_id == case_uuid)
    )
    await session.execute(delete(Case).where(Case.id == case_uuid))
    await session.commit()
    logger.info("deleted case %s with %d documents and %d cache keys", case_id, len(doc_ids), deleted_keys)
    return {"deleted": case_id, "documents_deleted": str(len(doc_ids)), "cache_keys_deleted": str(deleted_keys)}


@router.get("/{case_id}/report/pdf")
async def download_report(
    case_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    case = await _get_owned_case(case_id, user, session)

    doc_result = await session.execute(
        select(Document).where(Document.case_id == case.id).order_by(Document.created_at)
    )
    documents = doc_result.scalars().all()

    doc_ids = [d.id for d in documents]
    clause_map: dict[uuid.UUID, list] = {did: [] for did in doc_ids}
    anomaly_map: dict[uuid.UUID, dict] = {}

    if doc_ids:
        clause_result = await session.execute(
            select(Clause).where(Clause.document_id.in_(doc_ids)).order_by(Clause.page_number)
        )
        clauses = clause_result.scalars().all()
        clause_ids = [c.id for c in clauses]
        for c in clauses:
            clause_map[c.document_id].append(c)

        if clause_ids:
            anomaly_result = await session.execute(
                select(Anomaly).where(Anomaly.clause_id.in_(clause_ids))
            )
            for a in anomaly_result.scalars().all():
                anomaly_map[a.clause_id] = a

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    total_anomalies = len(anomaly_map)
    high_count = sum(1 for a in anomaly_map.values() if a.severity == "high")
    medium_count = sum(1 for a in anomaly_map.values() if a.severity == "medium")
    low_count = sum(1 for a in anomaly_map.values() if a.severity == "low")
    unreviewed_count = sum(1 for a in anomaly_map.values() if not a.reviewed)

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 14, text="ClauseBridge Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, text=_safe_text(f"Case: {case.title}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, text=f"Generated: {datetime.now(UTC).strftime('%B %d, %Y')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, text="Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, text=f"Total Documents: {len(documents)}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Total Anomalies: {total_anomalies}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"High: {high_count}   Medium: {medium_count}   Low: {low_count}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, text=f"Awaiting Review: {unreviewed_count}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, text="Document Overview", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for doc in documents:
        doc_clauses = clause_map.get(doc.id, [])
        doc_anomaly_count = sum(1 for c in doc_clauses if c.id in anomaly_map)
        doc_unreviewed = sum(1 for c in doc_clauses if c.id in anomaly_map and not anomaly_map[c.id].reviewed)
        doc_type = doc.document_type or "Unclassified"
        pdf.cell(0, 7, text=_safe_text(f"  {doc.filename}"), new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, text=f"    Type: {doc_type}  |  Anomalies: {doc_anomaly_count}  |  Awaiting Review: {doc_unreviewed}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if unreviewed_count > 0:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, text="Anomalies Awaiting Review", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for clause_id, anomaly in anomaly_map.items():
            if anomaly.reviewed:
                continue
            clause_text = ""
            for doc_clauses in clause_map.values():
                for c in doc_clauses:
                    if c.id == clause_id:
                        clause_text = c.clause_type
                        break
            pdf.cell(0, 7, text=_safe_text(f"  [{anomaly.severity.upper()}] {clause_text}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    for doc in documents:
        doc_clauses = clause_map.get(doc.id, [])
        doc_anomalies = [(c, anomaly_map[c.id]) for c in doc_clauses if c.id in anomaly_map]
        doc_unreviewed = sum(1 for _, a in doc_anomalies if not a.reviewed)

        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, text=_safe_text(doc.filename), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        doc_type = _safe_text(doc.document_type or "Unclassified")
        conf = f"{doc.classification_confidence * 100:.0f}%" if doc.classification_confidence else "N/A"
        pdf.cell(0, 7, text=f"Type: {doc_type}  |  Confidence: {conf}  |  Status: {doc.status}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 7, text=f"Anomalies: {len(doc_anomalies)}  |  Awaiting Review: {doc_unreviewed}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        if not doc_anomalies:
            pdf.set_font("Helvetica", "I", 10)
            pdf.cell(0, 7, text="No anomalies detected.", new_x="LMARGIN", new_y="NEXT")
            continue

        for clause, anomaly in doc_anomalies:
            review_status = "PENDING REVIEW" if not anomaly.reviewed else "Reviewed"
            verified_status = "VERIFIED" if anomaly.verified else "UNVERIFIED"
            pdf.set_font("Helvetica", "B", 11)
            sev_label = anomaly.severity.upper()
            source_label = anomaly.source.replace("_", " ").title() if anomaly.source else "Unknown"
            pdf.cell(0, 8, text=_safe_text(f"[{sev_label}] {clause.clause_type} (Page {clause.page_number}) - {review_status} - {verified_status}"), new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("Helvetica", "", 9)
            pdf.cell(0, 6, text=f"Confidence: {anomaly.confidence * 100:.0f}%  |  Source: {source_label}", new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, text="Clause:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 5, text=_safe_text(clause.clause_text[:500]))

            if anomaly.matched_reference:
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(0, 6, text="Matched Reference:", new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", "I", 8)
                pdf.multi_cell(0, 5, text=_safe_text(anomaly.matched_reference[:500]))

            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, text="Reason:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 5, text=_safe_text(anomaly.reasons[:500]))
            pdf.ln(4)

    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)

    filename = f"clausebridge-report-{case.title.replace(' ', '-').lower()}.pdf"
    safe_filename = _safe_text(filename)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )
