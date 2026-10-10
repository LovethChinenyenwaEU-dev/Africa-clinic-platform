import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.identity.dependencies import CurrentStaff
from app.modules.tenancy.schemas import BranchResponse
from app.modules.tenancy.service import get_branch, list_branches

router = APIRouter(prefix="/tenancy", tags=["tenancy"])


@router.get("/branches", response_model=list[BranchResponse])
def list_my_branches(
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """The branches of the logged-in person's own clinic."""
    return list_branches(session, tenant_id=current_staff.tenant_id)


@router.get("/branches/{branch_id}", response_model=BranchResponse)
def read_branch(
    branch_id: uuid.UUID,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """One branch, if it belongs to the logged-in person's clinic."""
    branch = get_branch(session, tenant_id=current_staff.tenant_id, branch_id=branch_id)
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found.")
    return branch