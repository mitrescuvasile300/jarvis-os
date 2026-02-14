"""Tests for trading skill — checklist and rug-pull detection."""

import pytest
import asyncio

from skills.trading.actions import TradingSkill, DEFAULT_CHECKLIST, RUGPULL_SIGNALS


# Mock dependencies
class MockTools:
    async def execute(self, name, args):
        return "mock_response"


class MockMemory:
    async def store_knowledge(self, *a, **kw):
        pass

    async def get_working(self, *a, **kw):
        return None


class MockLLM:
    async def chat(self, *a, **kw):
        return {"text": "mock"}


@pytest.fixture
def trading_skill():
    return TradingSkill("trading", {"config": {}}, MockTools(), MockLLM(), MockMemory())


class TestChecklist:
    def test_10_criteria_exist(self):
        assert len(DEFAULT_CHECKLIST["criteria"]) == 10

    def test_min_score_is_8(self):
        assert DEFAULT_CHECKLIST["min_score"] == 8

    @pytest.mark.asyncio
    async def test_perfect_token_gets_buy(self, trading_skill):
        result = await trading_skill.evaluate_token({"token_data": {
            "name": "PERFECT",
            "dev_holding": 1, "top10_holders": 10, "insider_pct": 5,
            "bundler_pct": 3, "token_age": 20, "profit_traders": 20,
            "social_presence": True, "contract_address_visible": True,
            "community_quality": True, "holder_diversity": True,
        }})
        assert "10/10" in result
        assert "BUY" in result

    @pytest.mark.asyncio
    async def test_bad_token_gets_skip(self, trading_skill):
        result = await trading_skill.evaluate_token({"token_data": {
            "name": "BAD",
            "dev_holding": 50, "top10_holders": 80, "insider_pct": 60,
            "bundler_pct": 40, "token_age": 5, "profit_traders": 0,
            "social_presence": False, "contract_address_visible": False,
            "community_quality": False, "holder_diversity": False,
        }})
        assert "SKIP" in result

    @pytest.mark.asyncio
    async def test_borderline_token(self, trading_skill):
        # Exactly 8/10 should pass
        result = await trading_skill.evaluate_token({"token_data": {
            "name": "BORDER",
            "dev_holding": 3, "top10_holders": 15, "insider_pct": 10,
            "bundler_pct": 8, "token_age": 30, "profit_traders": 12,
            "social_presence": True, "contract_address_visible": True,
            "community_quality": False, "holder_diversity": False,
        }})
        assert "8/10" in result
        assert "BUY" in result

    @pytest.mark.asyncio
    async def test_position_sizing_on_buy(self, trading_skill):
        result = await trading_skill.evaluate_token({"token_data": {
            "name": "GOOD",
            "dev_holding": 2, "top10_holders": 15, "insider_pct": 10,
            "bundler_pct": 5, "token_age": 25, "profit_traders": 15,
            "social_presence": True, "contract_address_visible": True,
            "community_quality": True, "holder_diversity": True,
        }})
        assert "Position Sizing" in result
        assert "Stop loss" in result
        assert "Take profit" in result


class TestRugPullDetection:
    def test_8_signals_defined(self):
        assert len(RUGPULL_SIGNALS) == 8

    @pytest.mark.asyncio
    async def test_clean_token_no_flags(self, trading_skill):
        result = await trading_skill.detect_rugpull({"token_data": {
            "name": "CLEAN",
            "dev_pct": 3, "liquidity_locked": True,
            "sell_fail_rate": 0, "top5_pct": 20,
            "same_funding_count": 0,
            "has_twitter": True, "has_telegram": True, "has_website": True,
            "wash_trade_pct": 5, "is_copycat": False,
            "mint_authority_active": False,
        }})
        assert "LOW RISK" in result
        assert "0/8" in result

    @pytest.mark.asyncio
    async def test_obvious_rug_critical(self, trading_skill):
        result = await trading_skill.detect_rugpull({"token_data": {
            "name": "RUGGED",
            "dev_pct": 30, "liquidity_locked": False,
            "sell_fail_rate": 90, "top5_pct": 70,
            "same_funding_count": 8,
            "has_twitter": False, "has_telegram": False, "has_website": False,
            "wash_trade_pct": 60, "is_copycat": True,
            "mint_authority_active": True,
        }})
        assert "CRITICAL" in result
        assert "8/8" in result

    @pytest.mark.asyncio
    async def test_honeypot_detected(self, trading_skill):
        result = await trading_skill.detect_rugpull({"token_data": {
            "name": "HONEYPOT",
            "sell_fail_rate": 80,
            "dev_pct": 2, "liquidity_locked": True,
            "top5_pct": 15, "same_funding_count": 0,
            "has_twitter": True, "has_telegram": True, "has_website": True,
            "wash_trade_pct": 5, "is_copycat": False,
            "mint_authority_active": False,
        }})
        assert "honeypot_pattern" in result

    @pytest.mark.asyncio
    async def test_disclaimer_always_shown(self, trading_skill):
        result = await trading_skill.detect_rugpull({"token_data": {"name": "ANY"}})
        assert "Disclaimer" in result
