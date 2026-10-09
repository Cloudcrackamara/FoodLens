from enum import StrEnum


class DataMode(StrEnum):
    DEMO = "DEMO"


class CompanyType(StrEnum):
    MANUFACTURER = "MANUFACTURER"
    WHOLESALER = "WHOLESALER"
    BOTH = "BOTH"


class CompanyReviewStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


class ReviewStatus(StrEnum):
    """Batches and supplier locations."""

    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ProductStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class MemberRole(StrEnum):
    OWNER = "OWNER"
    REPRESENTATIVE = "REPRESENTATIVE"


class MembershipStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class RegisterStatus(StrEnum):
    """Status stored in the simulated regulator register. Expiry is computed from expires_on."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ChangeNoticeStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ChangeType(StrEnum):
    PACKAGING = "PACKAGING"
    LABEL = "LABEL"
    PRODUCT_DETAILS = "PRODUCT_DETAILS"
    BATCH_DETAILS = "BATCH_DETAILS"
    LOCATION_DETAILS = "LOCATION_DETAILS"
    OTHER = "OTHER"


class AttachmentMimeType(StrEnum):
    PDF = "application/pdf"
    PNG = "image/png"
    JPEG = "image/jpeg"


class AnnouncementStatus(StrEnum):
    LIVE = "LIVE"
    HIDDEN = "HIDDEN"


class OrderStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"


class FulfilmentMethod(StrEnum):
    PICKUP = "PICKUP"
    DELIVERY = "DELIVERY"


class LookupResult(StrEnum):
    """One primary state per lookup, checked in this order (docs/DECISIONS.md D80-D84)."""

    INSUFFICIENT_OR_AMBIGUOUS = "INSUFFICIENT_OR_AMBIGUOUS"
    REGISTRATION_NOT_FOUND = "REGISTRATION_NOT_FOUND"
    REGISTRATION_EXPIRED_OR_INACTIVE = "REGISTRATION_EXPIRED_OR_INACTIVE"
    REGISTRATION_MISMATCH = "REGISTRATION_MISMATCH"
    REGISTERED_ACTIVE = "REGISTERED_ACTIVE"
