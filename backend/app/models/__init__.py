"""SQLModel table models. Import every model module here so Alembic autogenerate sees it."""

from app.models.catalogue import CredentialRecord, Product, ProductBatch, RegulatoryAgency
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

__all__ = [
    "AppUser",
    "AuditLog",
    "ChangeNotice",
    "ChangeNoticeField",
    "Company",
    "CompanyMember",
    "CredentialRecord",
    "NoticeAttachment",
    "OrderBatchAllocation",
    "OrderLine",
    "Product",
    "ProductAnnouncement",
    "ProductBatch",
    "RegulatoryAgency",
    "SupplierLocation",
    "UserSession",
    "WholesaleOrder",
]
