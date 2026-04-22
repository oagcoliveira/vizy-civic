"""
Digest API Router
=================
Endpoints:
  POST /digests/estimate   — pre-flight cost check
  POST /digests            — create and launch async digest generation
  GET  /digests            — list user's digests (history)
  GET  /digests/{id}       — get a single digest
  DELETE /digests/{id}     — delete a digest
"""

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.digest import Digest
from app.routers.auth import get_current_user
from app.models.auth import User
from app.services.digest_generator import (
    estimate_digest_cost,
    launch_digest_generation,
    MODEL_CONFIGS,
    COST_BLOCK_THRESHOLD,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class DigestEstimateRequest(BaseModel):
    deputy_ids: list[int] = []
    bill_ids: list[int] = []
    date_range: str = "last_7"   # yesterday | last_7 | last_15 | last_30 | last_60
    enrichment: bool = False
    model: str = "haiku"         # haiku | sonnet


class DigestCreateRequest(BaseModel):
    deputy_ids: list[int] = []
    bill_ids: list[int] = []
    date_range: str = "last_7"
    language: str = "pt"         # pt | en
    enrichment: bool = False
    model: str = "haiku"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_DATE_RANGES = {"yesterday", "last_7", "last_15", "last_30", "last_60"}
MAX_ITEMS = 10


def _validate_request(deputy_ids: list, bill_ids: list, date_range: str, model: str):
    total = len(deputy_ids) + len(bill_ids)
    if total == 0:
        raise HTTPException(status_code=400, detail="Select at least one deputy or bill.")
    if total > MAX_ITEMS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_ITEMS} combined deputies and bills allowed. You selected {total}.",
        )
    if date_range not in VALID_DATE_RANGES:
        raise HTTPException(status_code=400, detail=f"Invalid date_range. Choose from: {', '.join(VALID_DATE_RANGES)}")
    if model not in MODEL_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Invalid model. Choose from: {', '.join(MODEL_CONFIGS.keys())}")


def _auto_label(deputy_ids: list, bill_ids: list) -> str:
    parts = []
    if deputy_ids:
        n = len(deputy_ids)
        parts.append(f"{n} {'deputy' if n == 1 else 'deputies'}")
    if bill_ids:
        n = len(bill_ids)
        parts.append(f"{n} {'bill' if n == 1 else 'bills'}")
    today = date.today().strftime("%b %d %Y")
    return f"Digest — {', '.join(parts)} — {today}"


def _digest_to_dict(d: Digest) -> dict:
    return {
        "id": str(d.id),
        "label": d.label,
        "status": d.status,
        "parameters": d.parameters,
        "content": d.content,
        "estimated_cost_usd": float(d.estimated_cost) if d.estimated_cost else None,
        "error_message": d.error_message,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "completed_at": d.completed_at.isoformat() if d.completed_at else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/estimate")
def estimate_digest(
    req: DigestEstimateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Pre-flight check: calculates estimated cost and identifies inactive items.
    Does NOT create a digest record.
    """
    _validate_request(req.deputy_ids, req.bill_ids, req.date_range, req.model)

    result = estimate_digest_cost(
        db=db,
        deputy_ids=req.deputy_ids,
        bill_ids=req.bill_ids,
        date_range=req.date_range,
        enrichment=req.enrichment,
        model_key=req.model,
    )

    result["cost_limit_usd"] = COST_BLOCK_THRESHOLD
    result["model_label"] = MODEL_CONFIGS[req.model]["label"]
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
def create_digest(
    req: DigestCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new digest and launch async generation.
    Returns the digest record immediately with status='processing'.
    """
    _validate_request(req.deputy_ids, req.bill_ids, req.date_range, req.model)

    # Run estimate to check cost and get active items
    estimate = estimate_digest_cost(
        db=db,
        deputy_ids=req.deputy_ids,
        bill_ids=req.bill_ids,
        date_range=req.date_range,
        enrichment=req.enrichment,
        model_key=req.model,
    )

    if estimate["blocked"]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Estimated cost ${estimate['estimated_cost_usd']:.4f} exceeds the "
                f"${COST_BLOCK_THRESHOLD:.2f} limit. Reduce the number of items or the date range."
            ),
        )

    # Only include active items
    active_deputy_ids = [d["id"] for d in estimate["active_deputies"]]
    active_bill_ids = [b["id"] for b in estimate["active_bills"]]

    if not active_deputy_ids and not active_bill_ids:
        raise HTTPException(
            status_code=400,
            detail="No activity found for any of the selected items in the chosen date range.",
        )

    params = {
        "deputy_ids": active_deputy_ids,
        "bill_ids": active_bill_ids,
        "date_range": req.date_range,
        "language": req.language,
        "enrichment": req.enrichment,
        "model": req.model,
    }

    digest = Digest(
        user_id=current_user.id,
        label=_auto_label(active_deputy_ids, active_bill_ids),
        status="processing",
        parameters=params,
        estimated_cost=estimate["estimated_cost_usd"],
    )
    db.add(digest)
    db.commit()
    db.refresh(digest)

    # Launch background generation
    launch_digest_generation(str(digest.id), params)

    return _digest_to_dict(digest)


@router.get("")
def list_digests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all digests for the current user, newest first."""
    digests = (
        db.query(Digest)
        .filter(Digest.user_id == current_user.id)
        .order_by(Digest.created_at.desc())
        .all()
    )
    return [_digest_to_dict(d) for d in digests]


@router.get("/{digest_id}")
def get_digest(
    digest_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve a single digest by ID."""
    try:
        uid = uuid.UUID(digest_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid digest ID.")

    digest = db.query(Digest).filter(
        Digest.id == uid,
        Digest.user_id == current_user.id,
    ).first()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found.")
    return _digest_to_dict(digest)


@router.delete("/{digest_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_digest(
    digest_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a digest."""
    try:
        uid = uuid.UUID(digest_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid digest ID.")

    digest = db.query(Digest).filter(
        Digest.id == uid,
        Digest.user_id == current_user.id,
    ).first()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found.")

    db.delete(digest)
    db.commit()
