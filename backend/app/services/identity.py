"""QR identities for units and cartons (D138, D139).

- A token is 16 bytes from `secrets.token_bytes` (128 bits, CSPRNG), encoded as 26 Crockford
  Base32 characters, upper-case, no padding. It is never derived from IDs, sequences or time.
- Typed codes are normalised before hashing: upper-case, spaces and hyphens removed, O read as 0,
  I and L read as 1.
- Only sha256(normalised token) hex is stored. Raw tokens leave this module only inside the
  one-time label file (services/labels.py); they are never stored or logged.
"""

import hashlib
import math
import secrets
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models import Carton, ProductUnit

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford Base32: no I, L, O, U
TOKEN_BYTES = 16
TOKEN_LENGTH = 26  # ceil(128 / 5)
MAX_ATTEMPTS = 5

_TYPING_FIXES = str.maketrans({"O": "0", "I": "1", "L": "1", " ": None, "-": None})


class IdentityGenerationError(Exception):
    """Fresh tokens kept colliding; practically impossible with 128-bit tokens."""


def encode(raw: bytes) -> str:
    """Big-endian Crockford Base32 of 16 bytes, left-padded to 26 characters."""
    number = int.from_bytes(raw, "big")
    chars = []
    for _ in range(TOKEN_LENGTH):
        number, digit = divmod(number, 32)
        chars.append(ALPHABET[digit])
    return "".join(reversed(chars))


def new_token() -> str:
    return encode(secrets.token_bytes(TOKEN_BYTES))


def normalise(code: str) -> str:
    """'7q2m-8kd3 xh4n…' -> '7Q2M8KD3XH4N…'; O -> 0, I/L -> 1. Other characters are kept, so an
    invalid code simply matches nothing."""
    return code.upper().translate(_TYPING_FIXES)


def token_hash(code: str) -> str:
    return hashlib.sha256(normalise(code).encode("ascii", "replace")).hexdigest()


def grouped(token: str) -> str:
    """Printed form under the QR: groups of 4, the last group has 2."""
    return " ".join(token[i : i + 4] for i in range(0, len(token), 4))


@dataclass(frozen=True)
class Identity:
    token: str
    hash: str


def _taken(db: Session, hashes: Iterable[str]) -> set[str]:
    hashes = list(hashes)
    taken: set[str] = set()
    for model in (ProductUnit, Carton):
        taken.update(
            db.exec(select(model.qr_token_hash).where(model.qr_token_hash.in_(hashes))).all()
        )
    return taken


def new_identities(
    db: Session, count: int, token_factory: Callable[[], str] = new_token
) -> list[Identity]:
    """`count` tokens whose hashes are unused by any unit or carton and by each other. Collided
    tokens are replaced, up to MAX_ATTEMPTS rounds. The unique constraints are the backstop."""
    identities: dict[str, Identity] = {}
    for _ in range(MAX_ATTEMPTS):
        needed = count - len(identities)
        if needed == 0:
            break
        fresh: dict[str, Identity] = {}
        for _ in range(needed):
            token = token_factory()
            digest = token_hash(token)
            if digest not in identities:
                fresh[digest] = Identity(token, digest)
        for digest in _taken(db, fresh):
            del fresh[digest]
        identities.update(fresh)
    if len(identities) != count:
        raise IdentityGenerationError
    return list(identities.values())


def carton_count(quantity: int, units_per_carton: int | None) -> int:
    return math.ceil(quantity / units_per_carton) if units_per_carton else 0
