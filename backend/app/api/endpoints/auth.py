from datetime import timedelta
import secrets
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.api import deps
from app.core import security
from app.core.config import settings
from app.models.user import User

router = APIRouter()

@router.post("/login/access-token")
def login_access_token(
    response: Response,
    db: Session = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = security.create_access_token(str(user.id), expires_delta=access_token_expires)
    csrf_token = secrets.token_urlsafe(32)
    secure = settings.SESSION_COOKIE_SECURE or settings.ENVIRONMENT.lower() in {"staging", "production"}
    response.set_cookie(
        deps.SESSION_COOKIE,
        token,
        max_age=int(access_token_expires.total_seconds()),
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        deps.CSRF_COOKIE,
        csrf_token,
        max_age=int(access_token_expires.total_seconds()),
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )
    return {"csrf_token": csrf_token, "token_type": "cookie"}


@router.get("/session")
def get_session(
    request: Request,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    csrf_token = request.cookies.get(deps.CSRF_COOKIE)
    if not csrf_token:
        raise HTTPException(status_code=401, detail="Session requires reauthentication")
    return {"csrf_token": csrf_token}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(deps.get_db), current_user: User = Depends(deps.get_current_user)) -> Any:
    from app.models.session import RevokedSession
    from datetime import datetime, timezone
    claims = request.state.session_claims
    db.merge(RevokedSession(id=claims["jti"], user_id=current_user.id, expires_at=datetime.fromtimestamp(claims["exp"], timezone.utc)))
    db.commit()
    secure = settings.SESSION_COOKIE_SECURE or settings.ENVIRONMENT.lower() in {"staging", "production"}
    response.delete_cookie(deps.SESSION_COOKIE, path="/", secure=secure, httponly=True, samesite="lax")
    response.delete_cookie(deps.CSRF_COOKIE, path="/", secure=secure, httponly=False, samesite="lax")
    return {"status": "signed_out"}
