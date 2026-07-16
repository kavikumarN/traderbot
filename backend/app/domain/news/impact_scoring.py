"""Keyword-based "how much should a trader care" scoring for a headline —
deterministic and explainable (every tag returned is a literal keyword
match), not a model call. Same trade-off as `app.domain.strategy.
pattern_recognition`: a trading platform needs to be able to say *why* it
flagged something.
"""

from __future__ import annotations

import re

from app.domain.news.enums import ImpactLevel

# Checked in order — a HIGH keyword anywhere wins outright over any number
# of MEDIUM matches; routine coverage that hits neither list is LOW.
_HIGH_IMPACT_KEYWORDS = [
    "sec charges",
    "sec sues",
    "lawsuit",
    "hacked",
    "hack",
    "exploit",
    "exploited",
    "regulation",
    "regulatory crackdown",
    "banned",
    "ban on",
    "etf approved",
    "etf approval",
    "etf rejected",
    "federal reserve",
    "interest rate",
    "rate hike",
    "rate cut",
    "bankruptcy",
    "files for bankruptcy",
    "collapse",
    "crash",
    "delisting",
    "delisted",
    "investigation",
    "fraud",
    "seized",
    "insolvent",
    "liquidation",
    "all-time high",
    "surges",
    "plunges",
    "plummets",
    "trading halted",
]

_MEDIUM_IMPACT_KEYWORDS = [
    "partnership",
    "listing",
    "lists",
    "upgrade",
    "hard fork",
    "integration",
    "launches",
    "launch",
    "acquisition",
    "acquires",
    "funding round",
    "investment",
    "adoption",
    "outage",
    "downtime",
    "airdrop",
]

# name/ticker -> canonical ticker symbol shown to the user.
_SYMBOL_ALIASES: dict[str, str] = {
    "bitcoin": "BTC",
    "btc": "BTC",
    "ethereum": "ETH",
    "eth": "ETH",
    "solana": "SOL",
    "sol": "SOL",
    "ripple": "XRP",
    "xrp": "XRP",
    "bnb": "BNB",
    "cardano": "ADA",
    "ada": "ADA",
    "dogecoin": "DOGE",
    "doge": "DOGE",
    "polkadot": "DOT",
    "dot": "DOT",
    "polygon": "MATIC",
    "matic": "MATIC",
    "avalanche": "AVAX",
    "avax": "AVAX",
    "chainlink": "LINK",
    "link": "LINK",
    "litecoin": "LTC",
    "ltc": "LTC",
    "tether": "USDT",
    "usdt": "USDT",
    "usdc": "USDC",
}


def _find_matches(text: str, keywords: list[str]) -> list[str]:
    matched: list[str] = []
    for keyword in keywords:
        if re.search(r"\b" + re.escape(keyword) + r"\b", text):
            matched.append(keyword)
    return matched


def score_article(title: str, summary: str) -> tuple[ImpactLevel, list[str], list[str]]:
    text = f"{title} {summary}".lower()

    high_matches = _find_matches(text, _HIGH_IMPACT_KEYWORDS)
    medium_matches = _find_matches(text, _MEDIUM_IMPACT_KEYWORDS)

    if high_matches:
        impact = ImpactLevel.HIGH
    elif medium_matches:
        impact = ImpactLevel.MEDIUM
    else:
        impact = ImpactLevel.LOW

    tags = sorted({*high_matches, *medium_matches})

    symbols: list[str] = []
    for alias, ticker in _SYMBOL_ALIASES.items():
        if re.search(r"\b" + re.escape(alias) + r"\b", text) and ticker not in symbols:
            symbols.append(ticker)

    return impact, tags, symbols
