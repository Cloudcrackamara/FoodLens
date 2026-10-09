"""Simulated regulator register: number normalisation, record lookup, status, name matching.

The register (regulator_register) is the only source of registration status (D80). It is seeded
fictional data, read-only through the API, and not NAFDAC's or SON's own system.
"""

import re
from datetime import date

from sqlmodel import Session, select

from app.models import RegulatorRegister, RegulatoryAgency
from app.models.enums import RegisterStatus
from app.schemas.lookup import RegisterRecord, RegisterRecordStatus

MAX_NUMBER_LENGTH = 64
_NUMBER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9./_-]*$")
# Label text a scanner or a person may copy along with the number, e.g. "NAFDAC REG NO:".
_LABEL_PREFIX = re.compile(
    r"^(?:NAFDAC|SON|MANCAP)?\s*(?:REG(?:ISTRATION)?\.?)?\s*(?:NO\.?|NUMBER|NUM\.?)?\s*[:#]?\s*",
    re.IGNORECASE,
)


def normalize_registration_number(value: str | None) -> str | None:
    """Upper-case, strip a leading label like "NAFDAC Reg No:", remove all whitespace.
    "nafdac reg no: demo-nafdac-0001" -> "DEMO-NAFDAC-0001". Empty becomes None."""
    if value is None:
        return None
    text = value.strip()
    stripped = _LABEL_PREFIX.sub("", text, count=1)
    # Only drop the label if something that looks like a number is left.
    if stripped.strip():
        text = stripped
    normalized = re.sub(r"\s+", "", text).upper()
    return normalized or None


def is_valid_registration_number(value: str) -> bool:
    return len(value) <= MAX_NUMBER_LENGTH and bool(_NUMBER_PATTERN.match(value))


def normalize_name(value: str | None) -> str:
    """Compare names ignoring capitals and spaces (D83)."""
    return re.sub(r"\s+", "", value or "").lower()


def find_record(db: Session, number: str) -> tuple[RegulatorRegister, RegulatoryAgency] | None:
    return db.exec(
        select(RegulatorRegister, RegulatoryAgency)
        .join(RegulatoryAgency, RegulatoryAgency.agency_id == RegulatorRegister.agency_id)
        .where(RegulatorRegister.registration_number == number)
    ).first()


def record_status(record: RegulatorRegister, today: date) -> RegisterRecordStatus:
    if record.status == RegisterStatus.INACTIVE:
        return RegisterRecordStatus.INACTIVE_IN_DEMO_REGISTER
    if record.expires_on is not None and record.expires_on < today:
        return RegisterRecordStatus.EXPIRED_IN_DEMO_REGISTER
    return RegisterRecordStatus.ACTIVE_IN_DEMO_REGISTER


def record_read(record: RegulatorRegister, agency: RegulatoryAgency, today: date) -> RegisterRecord:
    return RegisterRecord(
        agency=agency.name,
        scheme=agency.scheme,
        registration_number=record.registration_number,
        registered_product_name=record.registered_product_name,
        registered_company_name=record.registered_company_name,
        status=record_status(record, today),
        expires_on=record.expires_on,
        data_mode=record.data_mode,
        provenance=record.provenance,
        last_checked_on=record.last_checked_on,
    )


def register_label(agency: RegulatoryAgency) -> str:
    """'NAFDAC (simulated)' -> 'simulated NAFDAC register'."""
    short = agency.name.replace("(simulated)", "").strip()
    return f"simulated {short} register"
