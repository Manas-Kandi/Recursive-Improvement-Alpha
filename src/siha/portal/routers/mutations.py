"""Mutation management endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from siha.db import get_session
from siha.models import Mutation, MutationStatus
from siha.portal.auth import verify_auth
from siha.schemas import MutationItem, MutationActionResponse

router = APIRouter(prefix="/mutations", tags=["mutations"])


@router.get("", response_model=List[MutationItem])
def get_mutations(token: str = Depends(verify_auth)):
    """Get mutation history."""
    with get_session() as session:
        mutations = session.query(Mutation).order_by(Mutation.id.desc()).limit(100).all()
        return [
            MutationItem(
                id=m.id,
                kind=m.kind,
                target_id=m.target_id,
                before=m.before,
                after=m.after,
                rationale=m.rationale,
                status=m.status,
                benchmark_delta=m.benchmark_delta,
                created_ts=m.created_ts.isoformat(),
                decided_ts=m.decided_ts.isoformat() if m.decided_ts else None,
            )
            for m in mutations
        ]


@router.post("/{mutation_id}/approve", response_model=MutationActionResponse)
def approve_mutation(mutation_id: int, token: str = Depends(verify_auth)):
    """Approve a proposed mutation, applying it as a candidate version."""
    from siha.harness.mutator import Mutator

    with get_session() as session:
        mutation = session.get(Mutation, mutation_id)
        if not mutation:
            raise HTTPException(status_code=404, detail="Mutation not found")

        if mutation.status not in (MutationStatus.proposed, MutationStatus.pending):
            raise HTTPException(status_code=400, detail="Mutation is not in an approvable state")

        mutator = Mutator()
        mutator.apply_mutation(mutation)

        return MutationActionResponse(status="candidate")


@router.post("/{mutation_id}/reject", response_model=MutationActionResponse)
def reject_mutation(mutation_id: int, token: str = Depends(verify_auth)):
    """Reject a proposed or candidate mutation."""
    from siha.harness.mutator import Mutator

    with get_session() as session:
        mutation = session.get(Mutation, mutation_id)
        if not mutation:
            raise HTTPException(status_code=404, detail="Mutation not found")

        if mutation.status not in (MutationStatus.proposed, MutationStatus.pending, MutationStatus.candidate):
            raise HTTPException(status_code=400, detail="Mutation is not in a rejectable state")

        if mutation.status == MutationStatus.candidate:
            mutator = Mutator()
            mutator.rollback_mutation(mutation)
        else:
            mutation.status = MutationStatus.rejected
            session.commit()

        return MutationActionResponse(status="rejected")
