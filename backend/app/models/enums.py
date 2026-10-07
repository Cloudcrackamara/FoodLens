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
    """Batches, credentials, and supplier locations."""

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


class CredentialStatus(StrEnum):
    """Status stored in the demo record. Expiry is computed from valid_until, not stored."""

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
    CREDENTIAL_DETAILS = "CREDENTIAL_DETAILS"
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
