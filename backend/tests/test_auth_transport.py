import pytest
from fastapi import HTTPException
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
import jwt
from jwt import InvalidTokenError as JWTError
from types import SimpleNamespace
from uuid import uuid4
from starlette.requests import Request

from app.api.deps import get_current_user
from app.api.endpoints import auth
from app.core import security
from app.core.config import settings
from app.schemas.user import UserResponse


def request_with_cookies(method: str, cookies: str, headers=()) -> Request:
    return Request({
        "type": "http",
        "method": method,
        "scheme": "https",
        "path": "/api/regulations/",
        "raw_path": b"/api/regulations/",
        "query_string": b"",
        "headers": [(b"cookie", cookies.encode()), *headers],
        "client": ("127.0.0.1", 12345),
        "server": ("example.test", 443),
    })


def test_cookie_session_requires_csrf_header_for_mutations():
    request = request_with_cookies("POST", "regulaai_session=opaque; regulaai_csrf=expected")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(request=request, db=None, token=None)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "CSRF validation failed"


def test_cookie_session_accepts_matching_csrf_header_before_user_lookup():
    request = request_with_cookies(
        "POST",
        "regulaai_session=opaque; regulaai_csrf=expected",
        headers=[(b"x-csrf-token", b"expected")],
    )

    # CSRF passes; the intentionally invalid test JWT is rejected after the check.
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(request=request, db=None, token=None)
    assert exc_info.value.status_code == 401


def test_login_issues_http_only_session_cookie_without_exposing_access_token(monkeypatch):
    user = SimpleNamespace(email="analyst@example.test", hashed_password="hash", is_active=True, id="user-id")

    class UserQuery:
        def filter(self, *_conditions):
            return self

        def first(self):
            return user

    class Database:
        def query(self, _model):
            return UserQuery()

    monkeypatch.setattr(auth.security, "verify_password", lambda *_args: True)
    monkeypatch.setattr(auth.security, "create_access_token", lambda *_args, **_kwargs: "signed-session")
    monkeypatch.setattr(auth.settings, "ENVIRONMENT", "production")
    response = Response()
    form = OAuth2PasswordRequestForm(username="analyst@example.test", password="not-a-real-password")

    result = auth.login_access_token(response=response, db=Database(), form_data=form)

    cookies = response.headers.getlist("set-cookie")
    session_cookie = next(cookie for cookie in cookies if cookie.startswith("regulaai_session="))
    csrf_cookie = next(cookie for cookie in cookies if cookie.startswith("regulaai_csrf="))
    assert "HttpOnly" in session_cookie
    assert "Secure" in session_cookie
    assert "SameSite=lax" in session_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "access_token" not in result
    assert result["csrf_token"]


def test_access_token_is_bound_to_configured_issuer_and_audience():
    token = security.create_access_token("test-user", expires_delta=timedelta(minutes=5))
    claims = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[security.ALGORITHM],
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
    )
    assert claims["sub"] == "test-user"
    assert claims["iss"] == settings.JWT_ISSUER
    assert claims["aud"] == settings.JWT_AUDIENCE
    assert claims["jti"]
    with pytest.raises(JWTError):
        jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[security.ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience="another-service",
        )


def test_authenticated_subject_is_normalized_to_uuid_before_database_lookup():
    user_id = uuid4()
    user = SimpleNamespace(id=user_id, is_active=True)

    class Query:
        conditions = ()

        def filter(self, *conditions):
            self.conditions = conditions
            return self

        def first(self):
            return user

    class Database:
        query_object = Query()

        def query(self, _model):
            if _model.__name__ == "RevokedSession":
                class Revocations:
                    def filter(self, *args): return self
                    def first(self): return None
                return Revocations()
            return self.query_object

    db = Database()
    token = security.create_access_token(str(user_id), expires_delta=timedelta(minutes=5))
    resolved = get_current_user(
        request=request_with_cookies("GET", ""),
        db=db,
        token=token,
    )

    assert resolved is user
    assert db.query_object.conditions[0].right.value == user_id


def test_user_response_matches_persisted_user_fields():
    user_id = uuid4()
    user = SimpleNamespace(
        id=user_id,
        email="reviewer@example.test",
        full_name="Synthetic Reviewer",
        is_active=True,
        created_at=None,
    )

    response = UserResponse.model_validate(user)

    assert response.id == user_id
    assert response.is_active is True
