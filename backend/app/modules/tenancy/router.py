import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.modules.identity.dependencies import CurrentStaff, require
from app.modules.identity.permissions import Capability
from app.modules.tenancy.schemas import BranchCreate, BranchResponse
from app.modules.tenancy.service import create_branch, get_branch, list_branches

router = APIRouter(prefix="/tenancy", tags=["tenancy"])


@router.get(
    "/branches",
    response_model=list[BranchResponse],
    dependencies=[Depends(require(Capability.BRANCH_READ))],
)
def list_my_branches(
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """The branches of the logged-in person's own clinic."""
    return list_branches(session, tenant_id=current_staff.tenant_id)


@router.post(
    "/branches",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require(Capability.BRANCH_WRITE))],
)
def create_my_branch(
    body: BranchCreate,
    current_staff: CurrentStaff,
    session: Session = Depends(get_session),
):
    """Add a branch to the logged-in admin's own clinic."""
    try:
        return create_branch(
            session,
            tenant_id=current_staff.tenant_id,
            name=body.name,
            city=body.city,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from None


@router.get(
    "/branches/{branch_id}",
    response_model=BranchResponse,
    dependencies=[Depends(require(Capability.BRANCH_READ))],
)
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