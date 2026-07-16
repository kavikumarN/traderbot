from __future__ import annotations

import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import EntityNotFoundError
from app.domain.risk.entities import RiskRule
from app.domain.risk.repositories import RiskRuleRepository
from app.infrastructure.db.models import RiskRuleModel, StrategyModel


def _to_domain(model: RiskRuleModel) -> RiskRule:
    return RiskRule(
        id=model.id,
        user_id=model.user_id,
        rule_type=model.rule_type,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
        strategy_id=model.strategy_id,
        threshold=model.threshold,
        config=dict(model.config),
    )


class SqlAlchemyRiskRuleRepository(RiskRuleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, rule: RiskRule) -> None:
        self._session.add(
            RiskRuleModel(
                id=rule.id,
                user_id=rule.user_id,
                strategy_id=rule.strategy_id,
                rule_type=rule.rule_type,
                threshold=rule.threshold,
                is_active=rule.is_active,
                config=rule.config,
                created_at=rule.created_at,
                updated_at=rule.updated_at,
            )
        )
        await self._session.flush()

    async def get_by_id(self, rule_id: uuid.UUID) -> RiskRule | None:
        model = await self._session.get(RiskRuleModel, rule_id)
        return _to_domain(model) if model else None

    async def list_for_user(self, user_id: uuid.UUID) -> list[RiskRule]:
        stmt = select(RiskRuleModel).where(RiskRuleModel.user_id == user_id)
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def list_active_for_strategy(self, strategy_id: uuid.UUID) -> list[RiskRule]:
        owning_user_id = select(StrategyModel.user_id).where(StrategyModel.id == strategy_id).scalar_subquery()
        stmt = select(RiskRuleModel).where(
            RiskRuleModel.is_active.is_(True),
            or_(
                RiskRuleModel.strategy_id == strategy_id,
                and_(RiskRuleModel.strategy_id.is_(None), RiskRuleModel.user_id == owning_user_id),
            ),
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def update(self, rule: RiskRule) -> None:
        model = await self._session.get(RiskRuleModel, rule.id)
        if model is None:
            raise EntityNotFoundError("RiskRule", rule.id)

        model.threshold = rule.threshold
        model.is_active = rule.is_active
        model.config = rule.config
        model.updated_at = rule.updated_at
        await self._session.flush()

    async def delete(self, rule_id: uuid.UUID) -> None:
        model = await self._session.get(RiskRuleModel, rule_id)
        if model is None:
            raise EntityNotFoundError("RiskRule", rule_id)
        await self._session.delete(model)
        await self._session.flush()
