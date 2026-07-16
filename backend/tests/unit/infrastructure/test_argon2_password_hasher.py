from __future__ import annotations

from app.domain.value_objects.password import PlainPassword
from app.infrastructure.security.argon2_password_hasher import Argon2PasswordHasher


def test_hash_then_verify_round_trip() -> None:
    hasher = Argon2PasswordHasher()
    hashed = hasher.hash(PlainPassword("correcthorse1", min_length=10))

    assert hasher.verify("correcthorse1", hashed) is True


def test_verify_rejects_wrong_password() -> None:
    hasher = Argon2PasswordHasher()
    hashed = hasher.hash(PlainPassword("correcthorse1", min_length=10))

    assert hasher.verify("wrong-password", hashed) is False


def test_verify_rejects_malformed_hash_without_raising() -> None:
    hasher = Argon2PasswordHasher()
    assert hasher.verify("anything", "not-a-real-argon2-hash") is False


def test_hash_is_salted_and_never_equals_the_plaintext() -> None:
    hasher = Argon2PasswordHasher()
    hashed_once = hasher.hash(PlainPassword("correcthorse1", min_length=10))
    hashed_twice = hasher.hash(PlainPassword("correcthorse1", min_length=10))

    assert hashed_once != "correcthorse1"
    assert hashed_once != hashed_twice  # different salt each time


def test_needs_rehash_is_false_for_a_freshly_produced_hash() -> None:
    hasher = Argon2PasswordHasher()
    hashed = hasher.hash(PlainPassword("correcthorse1", min_length=10))

    assert hasher.needs_rehash(hashed) is False
