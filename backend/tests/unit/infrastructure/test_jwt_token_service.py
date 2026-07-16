from __future__ import annotations

import time
import uuid

import jwt
import pytest

from app.domain.exceptions import InvalidTokenError
from app.infrastructure.security.jwt_token_service import JwtTokenService


def make_service(access_token_expire_minutes: int = 15) -> JwtTokenService:
    return JwtTokenService(
        secret_key="test-secret-key-thats-long-enough-1234567890",
        algorithm="HS256",
        access_token_expire_minutes=access_token_expire_minutes,
        refresh_token_expire_days=7,
    )


def test_create_then_decode_access_token_round_trip() -> None:
    service = make_service()
    user_id = uuid.uuid4()

    issued = service.create_access_token(user_id=user_id, email="a@b.com", role_names={"trader", "viewer"})
    payload = service.decode_access_token(issued.token)

    assert payload.user_id == user_id
    assert payload.email == "a@b.com"
    assert payload.role_names == frozenset({"trader", "viewer"})
    assert payload.jti == issued.payload.jti


def test_decode_rejects_tampered_signature() -> None:
    service = make_service()
    issued = service.create_access_token(user_id=uuid.uuid4(), email="a@b.com", role_names=set())
    tampered = issued.token[:-2] + ("aa" if issued.token[-2:] != "aa" else "bb")

    with pytest.raises(InvalidTokenError):
        service.decode_access_token(tampered)


def test_decode_rejects_token_signed_with_a_different_secret() -> None:
    service_a = make_service()
    service_b = JwtTokenService(
        secret_key="a-completely-different-secret-key-000000",
        algorithm="HS256",
        access_token_expire_minutes=15,
        refresh_token_expire_days=7,
    )
    issued = service_a.create_access_token(user_id=uuid.uuid4(), email="a@b.com", role_names=set())

    with pytest.raises(InvalidTokenError):
        service_b.decode_access_token(issued.token)


def test_decode_rejects_expired_token() -> None:
    service = make_service(access_token_expire_minutes=0)
    issued = service.create_access_token(user_id=uuid.uuid4(), email="a@b.com", role_names=set())
    time.sleep(1.1)  # cross the exp boundary; jwt.decode has no leeway configured

    with pytest.raises(InvalidTokenError):
        service.decode_access_token(issued.token)


def test_decode_rejects_malformed_token() -> None:
    service = make_service()
    with pytest.raises(InvalidTokenError):
        service.decode_access_token("not.a.jwt")


def test_decode_rejects_token_missing_required_claims() -> None:
    service = make_service()
    bare_token = jwt.encode({"sub": str(uuid.uuid4())}, "test-secret-key-thats-long-enough-1234567890", algorithm="HS256")

    with pytest.raises(InvalidTokenError):
        service.decode_access_token(bare_token)


def test_refresh_token_is_random_and_unique() -> None:
    service = make_service()
    first = service.generate_refresh_token()
    second = service.generate_refresh_token()

    assert first != second
    assert len(first) > 32


def test_refresh_token_hash_is_deterministic() -> None:
    service = make_service()
    raw = service.generate_refresh_token()

    assert service.hash_refresh_token(raw) == service.hash_refresh_token(raw)
    assert service.hash_refresh_token(raw) != raw


def test_refresh_token_ttl_seconds_matches_configured_days() -> None:
    service = JwtTokenService(
        secret_key="test-secret-key-thats-long-enough-1234567890",
        algorithm="HS256",
        access_token_expire_minutes=15,
        refresh_token_expire_days=3,
    )
    assert service.refresh_token_ttl_seconds() == 3 * 24 * 3600
