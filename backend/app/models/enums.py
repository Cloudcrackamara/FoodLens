from enum import StrEnum


class DataMode(StrEnum):
    DEMO = "DEMO"


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
    DISCONTINUED = "DISCONTINUED"


class MemberRole(StrEnum):
    OWNER = "OWNER"
    STAFF = "STAFF"


class MembershipStatus(StrEnum):
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
    """REQUESTED -> ACCEPTED | DECLINED | CANCELLED; ACCEPTED -> FULFILLED (D96)."""

    REQUESTED = "REQUESTED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"


class FulfilmentMethod(StrEnum):
    PICKUP = "PICKUP"
    DELIVERY = "DELIVERY"


class AnnouncementKind(StrEnum):
    NOTICE = "NOTICE"
    RECALL = "RECALL"


# --- Unit identity and lifecycle (D112, D138, D140) -------------------------------------------


class LifecycleStatus(StrEnum):
    """Derived by replaying lifecycle events; written only by services/lifecycle.py."""

    ISSUED = "ISSUED"
    RELEASED = "RELEASED"
    IN_TRANSIT = "IN_TRANSIT"
    IN_STOCK = "IN_STOCK"
    SOLD = "SOLD"
    RECALLED = "RECALLED"
    VOIDED = "VOIDED"


class LifecycleEventType(StrEnum):
    ISSUED = "ISSUED"
    RELEASED = "RELEASED"
    TRANSFERRED = "TRANSFERRED"
    RECEIVED = "RECEIVED"
    SOLD = "SOLD"
    RETURNED = "RETURNED"
    SALE_CORRECTED = "SALE_CORRECTED"
    RECALLED = "RECALLED"
    VOIDED = "VOIDED"


class EventSource(StrEnum):
    MANUFACTURER = "MANUFACTURER"
    MERCHANT_APP = "MERCHANT_APP"
    POS_API = "POS_API"
    CONSUMER_CHECK = "CONSUMER_CHECK"
    SYSTEM = "SYSTEM"


# --- Consumer checks (D115, D138, D141) -------------------------------------------------------


class IdentifierType(StrEnum):
    QR = "QR"
    TYPED = "TYPED"


class CheckResult(StrEnum):
    """One main result per check, in precedence order (D115, D141), plus CARTON_CODE (D148)."""

    INVALID_IDENTITY = "INVALID_IDENTITY"
    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY"
    BATCH_OR_PRODUCT_WARNING = "BATCH_OR_PRODUCT_WARNING"
    RECOGNISED_JUST_SOLD = "RECOGNISED_JUST_SOLD"
    RECOGNISED_PREVIOUSLY_SOLD = "RECOGNISED_PREVIOUSLY_SOLD"
    RECOGNISED_NOT_SOLD = "RECOGNISED_NOT_SOLD"
    # A recognised carton QR. Logged apart, so carton scans never count as pack checks (D148).
    CARTON_CODE = "CARTON_CODE"


class ConcernType(StrEnum):
    PREVIOUSLY_SOLD = "PREVIOUSLY_SOLD"
    SUSPICIOUS_RESULT = "SUSPICIOUS_RESULT"
    PACKAGING = "PACKAGING"
    OTHER = "OTHER"


class ReportStatus(StrEnum):
    NEW = "NEW"
    REVIEWED = "REVIEWED"
    CLOSED = "CLOSED"


class RateLimitBucket(StrEnum):
    CHECK = "CHECK"
    REPORT = "REPORT"
    LOGIN = "LOGIN"
    REGISTER = "REGISTER"
    POS = "POS"


# --- Risk alerts (D125, D143) ----------------------------------------------------------------


class RiskRule(StrEnum):
    R1_SCAN_AFTER_SALE_ELSEWHERE = "R1_SCAN_AFTER_SALE_ELSEWHERE"
    R2_IMPOSSIBLE_TRAVEL = "R2_IMPOSSIBLE_TRAVEL"
    R3_SCAN_VOLUME = "R3_SCAN_VOLUME"
    R4_INVALID_BURST = "R4_INVALID_BURST"
    R5_POS_UNAVAILABLE_UNIT = "R5_POS_UNAVAILABLE_UNIT"
    R6_UNRELEASED_SCANNED = "R6_UNRELEASED_SCANNED"
    R7_CUSTODY_CONFLICT = "R7_CUSTODY_CONFLICT"
    R8_VOIDED_CODE_IN_USE = "R8_VOIDED_CODE_IN_USE"
    R9_MORE_OBSERVED_THAN_ALLOCATED = "R9_MORE_OBSERVED_THAN_ALLOCATED"


class AlertLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AlertStatus(StrEnum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED_LEGITIMATE = "RESOLVED_LEGITIMATE"
    RESOLVED_SUSPECTED_COPY = "RESOLVED_SUSPECTED_COPY"


# --- POS integration (D121) ------------------------------------------------------------------


class PosPartnerStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class PosLinkStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
