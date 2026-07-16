from __future__ import annotations

import pytest

from app.domain.exceptions import ValidationError
from app.domain.value_objects.email import Email
from app.domain.value_objects.password import PlainPassword


class TestEmail:
    def test_normalizes_case_and_whitespace(self) -> None:
        assert Email("  Alice@Example.COM ").value == "alice@example.com"

    @pytest.mark.parametrize("raw", ["not-an-email", "missing-domain@", "@missing-local.com", "no-at-sign.com"])
    def test_rejects_invalid_format(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            Email(raw)

    def test_equality_is_value_based(self) -> None:
        assert Email("a@b.com") == Email("a@b.com")


class TestPlainPassword:
    def test_accepts_a_valid_password(self) -> None:
        password = PlainPassword("correcthorse1", min_length=10)
        assert password.value == "correcthorse1"

    def test_rejects_too_short(self) -> None:
        with pytest.raises(ValidationError):
            PlainPassword("short1", min_length=10)

    def test_rejects_missing_digit(self) -> None:
        with pytest.raises(ValidationError):
            PlainPassword("noDigitsHere", min_length=10)

    def test_rejects_missing_letter(self) -> None:
        with pytest.raises(ValidationError):
            PlainPassword("1234567890", min_length=10)

    def test_repr_never_leaks_the_value(self) -> None:
        password = PlainPassword("correcthorse1", min_length=10)
        assert "correcthorse1" not in repr(password)
        assert "correcthorse1" not in str(password)
