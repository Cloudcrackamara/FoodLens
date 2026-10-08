import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import MAX_PASSWORD_BYTES, MIN_PASSWORD_LENGTH
from app.models.enums import CompanyReviewStatus, MemberRole


class RegisterRequest(BaseModel):
    """Only these fields are read. Anything else the client sends (is_admin, is_active,
    review_status, user_id, ...) is ignored."""

    model_config = ConfigDict(extra="ignore")

    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes")
        return value

    @field_validator("display_name")
    @classmethod
    def display_name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Display name must not be blank")
        return value.strip()


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Plain string: login only looks the address up, it does not validate its format.
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class MembershipRead(BaseModel):
    company_id: uuid.UUID
    company_display_name: str
    company_review_status: CompanyReviewStatus
    role: MemberRole


class UserRead(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str
    is_admin: bool
    membership: MembershipRead | None
