from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import EntityNotFoundError
from app.domain.trading.entities import ExchangeAccount
from app.domain.trading.repositories import ExchangeAccountRepository
from app.infrastructure.db.models import ExchangeAccountModel


def _to_domain(model: ExchangeAccountModel) -> ExchangeAccount:
    return ExchangeAccount(
        id=model.id,
        user_id=model.user_id,
        exchange=model.exchange,
        label=model.label,
        api_key_ciphertext=model.api_key_ciphertext,
        api_key_last_four=model.api_key_last_four,
        is_testnet=model.is_testnet,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyExchangeAccountRepository(ExchangeAccountRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, account: ExchangeAccount) -> None:
        self._session.add(
            ExchangeAccountModel(
                id=account.id,
                user_id=account.user_id,
                exchange=account.exchange,
                label=account.label,
                api_key_ciphertext=account.api_key_ciphertext,
                api_key_last_four=account.api_key_last_four,
                is_testnet=account.is_testnet,
                status=account.status,
                created_at=account.created_at,
                updated_at=account.updated_at,
            )
        )
        await self._session.flush()

    async def get_by_id(self, account_id: uuid.UUID) -> ExchangeAccount | None:
        model = await self._session.get(ExchangeAccountModel, account_id)
        return _to_domain(model) if model else None

    async def list_for_user(self, user_id: uuid.UUID) -> list[ExchangeAccount]:
        stmt = (
            select(ExchangeAccountModel)
            .where(ExchangeAccountModel.user_id == user_id)
            .order_by(ExchangeAccountModel.created_at.desc())
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def update(self, account: ExchangeAccount) -> None:
        model = await self._session.get(ExchangeAccountModel, account.id)
        if model is None:
            raise EntityNotFoundError("ExchangeAccount", account.id)

        model.label = account.label
        model.status = account.status
        model.updated_at = account.updated_at
        await self._session.flush()
