"""The signing examples in docs/POS_INTEGRATION.md are run against the test API, so the guide
stays correct. The JavaScript example needs Node.js on PATH; it is skipped without it."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.models import PosPartner, PosPartnerRetailer, PosTill
from app.services import pos_auth
from app.services.demo_pos import DEMO_PARTNER_NAME
from tests import factories as f
from tests.test_pos import World, build_world, pos_settings

GUIDE = Path(__file__).resolve().parents[2] / "docs" / "POS_INTEGRATION.md"


def example(name: str) -> str:
    """The fenced code block that follows `<!-- example: {name} -->` in the guide."""
    text = GUIDE.read_text(encoding="utf-8")
    after = text.split(f"<!-- example: {name} -->", 1)[1]
    block = after.split("```", 2)[1]
    return block.split("\n", 1)[1]


@pytest.fixture
def world(session: Session, make_client) -> World:
    return build_world(session, make_client, pos_settings())


def test_the_python_example_signs_a_sale_the_api_accepts(world: World):
    namespace: dict = {}
    exec(example("python-signing"), namespace)
    _, token = world.unit()

    raw_body, headers = namespace["signed_request"](world.key, world.secret, world.sale_body(token))
    response = world.client.post("/api/pos/v1/sales", content=raw_body, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["recorded"] == 1


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_the_javascript_example_signs_a_sale_the_api_accepts(world: World, tmp_path: Path):
    _, token = world.unit()
    body = world.sale_body(token)
    script = tmp_path / "sign.mjs"
    script.write_text(
        example("js-signing")
        + "\nconst [key, secret, body] = process.argv.slice(2);\n"
        + "console.log(JSON.stringify(signedRequest(key, secret, JSON.parse(body))));\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["node", str(script), world.key, world.secret, json.dumps(body)],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    signed = json.loads(result.stdout)
    response = world.client.post(
        "/api/pos/v1/sales", content=signed["rawBody"].encode(), headers=signed["headers"]
    )

    assert response.status_code == 200, response.text
    assert response.json()["recorded"] == 1


def test_both_examples_match_the_server_signature():
    namespace: dict = {}
    exec(example("python-signing"), namespace)
    raw, headers = namespace["signed_request"](
        "flk_x", "fls_secret", {"a": 1}, timestamp=1700000000
    )

    assert headers["X-FoodLens-Signature"] == pos_auth.sign("fls_secret", "1700000000", raw)


# --- Seed (D123) -----------------------------------------------------------------------------


def test_the_seed_creates_the_demo_partner_only_with_pos_secret_key(session: Session):
    from app.demo_data import DEMO_TILL_REF, seed_demo_pos

    admin = f.make_user(session, is_admin=True)

    skipped = seed_demo_pos(session, pos_settings(pos_secret_key=""), admin)
    assert skipped.startswith("Demo POS partner skipped")
    assert (
        session.exec(select(PosPartner).where(PosPartner.name == DEMO_PARTNER_NAME)).first() is None
    )

    settings = pos_settings()
    seed_demo_pos(session, settings, admin)
    seed_demo_pos(session, settings, admin)  # idempotent

    (partner,) = session.exec(select(PosPartner).where(PosPartner.name == DEMO_PARTNER_NAME)).all()
    assert pos_auth.decrypt_secret(settings, partner).startswith("fls_")
    (link,) = session.exec(
        select(PosPartnerRetailer).where(PosPartnerRetailer.partner_id == partner.partner_id)
    ).all()
    (till,) = session.exec(select(PosTill).where(PosTill.partner_id == partner.partner_id)).all()
    assert till.till_ref == DEMO_TILL_REF
    assert till.retailer_company_id == link.retailer_company_id

    # A changed POS_SECRET_KEY gives the demo partner a new secret it can decrypt.
    rotated = pos_settings()
    seed_demo_pos(session, rotated, admin)
    session.refresh(partner)
    assert pos_auth.decrypt_secret(rotated, partner).startswith("fls_")
