import hmac
from typing import Generator, List, Optional
from uuid import UUID
from fastapi import Depends, HTTPException, Header, Request, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.core.rbac import Role, Permission, has_permission, is_role_allowed
from app.db.session import SessionLocal
from app.models.organization_member import OrganizationMember
from app.models.user import User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login/access-token", auto_error=False
)
SESSION_COOKIE = "regulaai_session"
CSRF_COOKIE = "regulaai_csrf"


def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(reusable_oauth2),
) -> User:
    # Header bearer auth is retained for non-browser clients. Browser sessions use
    # an HttpOnly cookie plus a double-submit CSRF token on every state-changing call.
    if not token:
        token = request.cookies.get(SESSION_COOKIE)
        if token and request.method not in {"GET", "HEAD", "OPTIONS"}:
            csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
            csrf_header = request.headers.get("X-CSRF-Token", "")
            if not csrf_cookie or not csrf_header or not hmac.compare_digest(
                csrf_cookie.encode("utf-8"), csrf_header.encode("utf-8")
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="CSRF validation failed",
                )
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[security.ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={"require": ["exp", "sub", "iss", "aud", "jti"]},
        )
        token_data = payload.get("sub")
        if token_data is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        subject_id = UUID(token_data)
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    from app.models.session import RevokedSession
    if db.query(RevokedSession).filter(RevokedSession.id == payload.get("jti", "")).first():
        raise HTTPException(401, "Session has been revoked")
    request.state.session_claims = payload
    user = db.query(User).filter(User.id == subject_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return user


def verify_membership(
    db: Session,
    user: User,
    organization_id: UUID,
    allowed_roles: Optional[List[str]] = None,
    required_permission: Optional[Permission | str] = None,
) -> OrganizationMember:
    """
    Verify that the user is a member of the organization,
    and optionally that their role is allowed or possesses the required permission.
    """
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == organization_id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this organization.",
        )

    if allowed_roles and not is_role_allowed(membership.role, allowed_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{membership.role}' does not have sufficient permissions. Required roles: {allowed_roles}",
        )

    if required_permission and not has_permission(membership.role, required_permission):
        perm_str = required_permission.value if isinstance(required_permission, Permission) else required_permission
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{membership.role}' lacks required permission: '{perm_str}'.",
        )

    return membership
