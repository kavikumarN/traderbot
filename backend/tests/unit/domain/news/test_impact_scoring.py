from __future__ import annotations

from app.domain.news.enums import ImpactLevel
from app.domain.news.impact_scoring import score_article


class TestScoreArticle:
    def test_high_impact_keyword_wins(self) -> None:
        impact, tags, symbols = score_article(
            "SEC charges exchange with fraud", "The listing announcement follows a lawsuit."
        )
        assert impact == ImpactLevel.HIGH
        assert "lawsuit" in tags
        assert "listing" in tags  # medium keywords still get returned as tags

    def test_medium_impact_keyword_without_high(self) -> None:
        impact, tags, _ = score_article("Exchange announces new partnership", "A funding round follows.")
        assert impact == ImpactLevel.MEDIUM
        assert "partnership" in tags
        assert "funding round" in tags

    def test_no_keyword_matches_is_low(self) -> None:
        impact, tags, symbols = score_article("Weekly market recap", "A quiet week for trading volumes.")
        assert impact == ImpactLevel.LOW
        assert tags == []
        assert symbols == []

    def test_extracts_symbol_mentions(self) -> None:
        _, _, symbols = score_article("Bitcoin and Ethereum rally as Solana lags", "BTC and ETH both gained.")
        assert set(symbols) == {"BTC", "ETH", "SOL"}

    def test_symbol_alias_matches_whole_words_only(self) -> None:
        # "adaptive" shouldn't match the "ada" (Cardano) alias.
        _, _, symbols = score_article("Adaptive trading strategies", "A look at adaptive risk models.")
        assert "ADA" not in symbols

    def test_matching_is_case_insensitive(self) -> None:
        impact, tags, symbols = score_article("BITCOIN CRASH amid REGULATION fears", "")
        assert impact == ImpactLevel.HIGH
        assert "crash" in tags
        assert "regulation" in tags
        assert "BTC" in symbols
