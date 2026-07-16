"""Shared column-type helpers for ORM models.

``portable_enum`` backs enum columns with a plain ``VARCHAR`` + ``CHECK``
constraint (``native_enum=False``) instead of a Postgres ``CREATE TYPE``.
Native enum types require an ``ALTER TYPE ... ADD VALUE`` migration (which
can't run inside a transaction block) every time a state machine grows a
new member — order/strategy/signal statuses in particular are expected to
change over this project's lifetime, so the portable form is used
everywhere for consistency. ``values_callable`` stores each member's
``.value`` rather than its ``.name``; for most of these ``StrEnum``s the two
are identical, but ``KlineInterval`` (``ONE_MINUTE = "1m"``) is not, so
this must not be left to the default.
"""

from __future__ import annotations

from enum import Enum
from typing import TypeVar

from sqlalchemy import Enum as SAEnum

E = TypeVar("E", bound=Enum)


def portable_enum(enum_cls: type[E], *, name: str | None = None) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name or f"{enum_cls.__name__.lower()}_enum",
        native_enum=False,
        validate_strings=True,
        values_callable=lambda cls: [member.value for member in cls],
        length=32,
    )
