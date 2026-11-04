"""QR tokens: 128-bit CSPRNG, Crockford Base32, normalisation, hashing, collision retry (D138)."""

import hashlib
import re
from collections.abc import Iterator

import pytest
from sqlmodel import Session

from app.services import identity
from tests import factories as f

CROCKFORD = re.compile(r"^[0-9ABCDEFGHJKMNPQRSTVWXYZ]{26}$")


def test_tokens_are_26_crockford_characters_and_unique() -> None:
    tokens = [identity.new_token() for _ in range(5000)]

    assert all(CROCKFORD.match(t) for t in tokens)
    assert len(set(tokens)) == len(tokens)
    # 128 bits in 26 x 5 = 130 bits: the first character carries only 3 bits.
    assert {t[0] for t in tokens} <= set("01234567")
    # Every other position uses the whole alphabet.
    assert len({t[-1] for t in tokens}) == 32


def test_tokens_come_from_16_bytes_of_secrets_token_bytes(monkeypatch) -> None:
    requested = []

    def fake_token_bytes(n: int) -> bytes:
        requested.append(n)
        return bytes(range(n))

    monkeypatch.setattr(identity.secrets, "token_bytes", fake_token_bytes)

    assert identity.new_token() == identity.encode(bytes(range(16)))
    assert requested == [16]


def test_encoding_is_big_endian_crockford() -> None:
    assert identity.encode(bytes(16)) == "0" * 26
    assert identity.encode(b"\xff" * 16) == "7" + "Z" * 25
    assert identity.encode((1).to_bytes(16, "big")) == "0" * 25 + "1"
    assert identity.encode((32).to_bytes(16, "big")) == "0" * 24 + "10"


@pytest.mark.parametrize(
    "typed",
    [
        "7q2m8kd3xh4n9vbt6c1rzj5wae",
        "7Q2M 8KD3 XH4N 9VBT 6C1R ZJ5W AE",
        "7Q2M-8KD3-XH4N-9VBT-6C1R-ZJ5W-AE",
        "7Q2M8KD3XH4N9VBT6CIRZJ5WAE",  # I typed for 1
        "7Q2M8KD3XH4N9VBT6CLRZJ5WAE",  # L typed for 1
        " 7q2m-8kd3 xh4n-9vbt 6clr-zj5w ae ",
    ],
)
def test_typing_variants_hash_like_the_clean_token(typed: str) -> None:
    clean = "7Q2M8KD3XH4N9VBT6C1RZJ5WAE"

    assert identity.token_hash(typed) == identity.token_hash(clean)
    assert identity.token_hash(clean) == hashlib.sha256(clean.encode()).hexdigest()


def test_letter_o_is_read_as_zero() -> None:
    assert identity.normalise("O0o") == "000"
    assert identity.token_hash("7Q2MOKD3") == identity.token_hash("7Q2M0KD3")


def test_printed_form_is_groups_of_four_with_a_last_group_of_two() -> None:
    assert identity.grouped("7Q2M8KD3XH4N9VBT6C1RZJ5WAE") == "7Q2M 8KD3 XH4N 9VBT 6C1R ZJ5W AE"


def _sequence(*tokens: str) -> Iterator[str]:
    return iter(tokens)


def test_duplicate_tokens_in_one_generation_are_replaced(session: Session) -> None:
    a, b, c = "A" * 26, "B" * 26, "C" * 26
    tokens = _sequence(a, a, b, c)

    issued = identity.new_identities(session, 3, token_factory=lambda: next(tokens))

    assert sorted(i.token for i in issued) == [a, b, c]


def test_token_already_in_the_database_is_retried(session: Session) -> None:
    company = f.make_company(session)
    batch = f.make_batch(session, f.make_product(session, company))
    taken, fresh = "D" * 26, "E" * 26
    f.make_unit(session, batch, qr_token_hash=identity.token_hash(taken))
    f.make_carton(session, batch, company, qr_token_hash=identity.token_hash("F" * 26))
    tokens = _sequence(taken, "F" * 26, fresh, "G" * 26)

    issued = identity.new_identities(session, 2, token_factory=lambda: next(tokens))

    assert sorted(i.token for i in issued) == [fresh, "G" * 26]


def test_endless_collisions_give_up(session: Session) -> None:
    with pytest.raises(identity.IdentityGenerationError):
        identity.new_identities(session, 2, token_factory=lambda: "H" * 26)
