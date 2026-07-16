from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.trading.entities import Wallet
from app.domain.trading.repositories import WalletRepository
from app.infrastructure.db.models import WalletModel


def _to_domain(model: WalletModel) -> Wallet:
    return Wallet(
        id=model.id,
        exchange_account_id=model.exchange_account_id,
        asset=model.asset,
        free=model.free,
        locked=model.locked,
        updated_at=model.updated_at,
    )


class SqlAlchemyWalletRepository(WalletRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, wallet: Wallet) -> None:
        stmt = insert(WalletModel).values(
            id=wallet.id,
            exchange_account_id=wallet.exchange_account_id,
            asset=wallet.asset,
            free=wallet.free,
            locked=wallet.locked,
            updated_at=wallet.updated_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[WalletModel.exchange_account_id, WalletModel.asset],
            set_={"free": wallet.free, "locked": wallet.locked, "updated_at": wallet.updated_at},
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get(self, exchange_account_id: uuid.UUID, asset: str) -> Wallet | None:
        stmt = select(WalletModel).where(
            WalletModel.exchange_account_id == exchange_account_id, WalletModel.asset == asset
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(model) if model else None

    async def list_for_account(self, exchange_account_id: uuid.UUID) -> list[Wallet]:
        stmt = select(WalletModel).where(WalletModel.exchange_account_id == exchange_account_id).order_by(
            WalletModel.asset
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]
