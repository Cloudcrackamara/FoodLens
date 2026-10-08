from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.auth import CurrentUser
from app.core.config import get_settings
from app.core.db import DbSession
from app.core.rate_limit import enforce_rate_limit
from app.models import AppUser
from app.schemas.auth import LoginRequest, MembershipRead, RegisterRequest, UserRead
from app.services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

INVALID_CREDENTIALS = "Invalid email or password"
EMAIL_TAKEN = "An account with this email already exists"


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _user_read(db: DbSession, user: AppUser) -> UserRead:
    membership = None
    found = auth_service.membership_with_company(db, user)
    if found is not None:
        member, company = found
        membership = MembershipRead(
            company_id=company.company_id,
            company_display_name=company.display_name,
            company_review_status=company.review_status,
            role=member.role,
        )
    return UserRead(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        is_admin=user.is_admin,
        membership=membership,
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest, request: Request, response: Response, db: DbSession
) -> UserRead:
    enforce_rate_limit(request, "register")
    try:
        user = auth_service.register_user(
            db, email=body.email, password=body.password, display_name=body.display_name
        )
    except auth_service.EmailAlreadyRegisteredError:
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN) from None
    _set_session_cookie(response, auth_service.create_session(db, user))
    return _user_read(db, user)


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response, db: DbSession) -> UserRead:
    # Checked before the password, so guessing is limited even for unknown emails.
    enforce_rate_limit(request, "login", auth_service.normalize_email(body.email))
    try:
        user = auth_service.authenticate(db, email=body.email, password=body.password)
    except auth_service.InvalidCredentialsError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS) from None
    _set_session_cookie(response, auth_service.create_session(db, user))
    return _user_read(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DbSession) -> None:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        auth_service.revoke_session(db, token)
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )


@router.get("/me")
def me(user: CurrentUser, db: DbSession) -> UserRead:
    return _user_read(db, user)
