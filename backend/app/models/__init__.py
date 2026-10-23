"""SQLModel table models. Import every model module here so Alembic autogenerate sees it."""

from app.models.allocation import AllocationCarton, AllocationUnit, BatchAllocation
from app.models.area import Area
from app.models.catalogue import Product, ProductBatch
from app.models.change import (
    AuditLog,
    ChangeNotice,
    ChangeNoticeField,
    NoticeAttachment,
    ProductAnnouncement,
)
from app.models.company import Company, CompanyMember, SupplierLocation
from app.models.identity import AppUser, UserSession
from app.models.order import OrderBatchAllocation, OrderLine, WholesaleOrder
from app.models.pos import PosPartner, PosPartnerKey, PosPartnerRetailer, PosTill
from app.models.risk import RiskAlert
from app.models.scan import ConsumerReport, RateLimitDaily, ScanEvent
from app.models.unit import Carton, LifecycleEvent, ProductUnit

__all__ = [
    "AllocationCarton",
    "AllocationUnit",
    "AppUser",
    "Area",
    "AuditLog",
    "BatchAllocation",
    "Carton",
    "ChangeNotice",
    "ChangeNoticeField",
    "Company",
    "CompanyMember",
    "ConsumerReport",
    "LifecycleEvent",
    "NoticeAttachment",
    "OrderBatchAllocation",
    "OrderLine",
    "PosPartner",
    "PosPartnerKey",
    "PosPartnerRetailer",
    "PosTill",
    "Product",
    "ProductAnnouncement",
    "ProductBatch",
    "ProductUnit",
    "RateLimitDaily",
    "RiskAlert",
    "ScanEvent",
    "SupplierLocation",
    "UserSession",
    "WholesaleOrder",
]
