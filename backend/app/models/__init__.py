"""SQLModel table models. Import every model module here so Alembic autogenerate sees it."""

from app.models.catalogue import Product, ProductBatch, RegulatorRegister, RegulatoryAgency
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
from app.models.scan import BatchScan

__all__ = [
    "AppUser",
    "AuditLog",
    "BatchScan",
    "ChangeNotice",
    "ChangeNoticeField",
    "Company",
    "CompanyMember",
    "NoticeAttachment",
    "OrderBatchAllocation",
    "OrderLine",
    "Product",
    "ProductAnnouncement",
    "ProductBatch",
    "RegulatorRegister",
    "RegulatoryAgency",
    "SupplierLocation",
    "UserSession",
    "WholesaleOrder",
]
