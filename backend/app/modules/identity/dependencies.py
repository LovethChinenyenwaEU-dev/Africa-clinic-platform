from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.core.db import get_session
from app.modules.identity.models import Staff
from app.modules.identity.permissions import Capability, role_has
from app.modules.identity.tokens import InvalidTokenError, decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def _not_authenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_staff(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> Staff:
    """The door guard: returns the logged-in staff member, or says 401.

    Any route that lists this in Depends(...) is automatically protected.
    """
    if credentials is None:
        raise _not_authenticated()

    try:
        claims = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise _not_authenticated() from None

    staff = session.get(Staff, claims.staff_id)
    if staff is None or not staff.is_active or staff.tenant_id != claims.tenant_id:
        raise _not_authenticated()
    return staff


CurrentStaff = Annotated[Staff, Depends(get_current_staff)]


def require(capability: Capability) -> Callable[..., Staff]:
    """Build a guard that needs one capability.

    Use it as: dependencies=[Depends(require(Capability.BRANCH_WRITE))]
    """

    def guard(current_staff: CurrentStaff) -> Staff:
        if not role_has(current_staff.role, capability):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to do this.",
            )
        return current_staff

    return guard