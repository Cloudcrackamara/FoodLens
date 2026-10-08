"""Reusable FastAPI auth dependencies. Every protected route uses one of these."""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.core.config import get_settings
from app.core.db import DbSession
from app.models import AppUser, CompanyMember
from app.models.enums import MemberRole
from app.services import auth as auth_service

NOT_SIGNED_IN = "Not signed in"
ADMIN_REQUIRED = "Admin access required"
NO_COMPANY_ACCESS = "You do not have access to this company"


def current_user(request: Request, db: DbSession) -> AppUser:
    """The signed-in user, or 401."""
    token = request.cookies.get(get_settings().session_cookie_name)
    user = auth_service.user_for_session_token(db, token) if token else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, NOT_SIGNED_IN)
    return user


CurrentUser = Annotated[AppUser, Depends(current_user)]


def require_admin(user: CurrentUser) -> AppUser:
    """A signed-in platform admin, or 403 (401 if not signed in)."""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, ADMIN_REQUIRED)
    return user


AdminUser = Annotated[AppUser, Depends(require_admin)]


def require_company_member(*roles: MemberRole) -> Callable[..., CompanyMember]:
    """Dependency factory for routes with a `company_id` path parameter.

    Passes only if the signed-in user is an active member of that company with one of
    `roles` (any role when none are given). Admins are not members and do not pass;
    admin actions use require_admin on their own routes.

        @router.patch("/companies/{company_id}")
        def edit(
            member: Annotated[CompanyMember, Depends(require_company_member(MemberRole.OWNER))],
        ): ...
    """
    allowed = set(roles) or set(MemberRole)

    def dependency(company_id: uuid.UUID, user: CurrentUser, db: DbSession) -> CompanyMember:
        member = auth_service.active_membership(db, user_id=user.user_id, company_id=company_id)
        if member is None or member.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, NO_COMPANY_ACCESS)
        return member

    return dependency
