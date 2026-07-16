from __future__ import annotations

from fastapi import APIRouter

from app.interface.api.v1 import (
    auth,
    insights,
    market,
    market_data,
    portfolio,
    risk,
    roles,
    strategies,
    trading,
    users,
)

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(roles.router)
api_v1_router.include_router(roles.permissions_router)
api_v1_router.include_router(market.router)
api_v1_router.include_router(market_data.router)
api_v1_router.include_router(trading.router)
api_v1_router.include_router(strategies.router)
api_v1_router.include_router(risk.router)
api_v1_router.include_router(portfolio.router)
api_v1_router.include_router(insights.router)
