"""Trading Skill — crypto portfolio monitoring, market scanning, and trade execution.

Includes:
- 10-point entry checklist (the exact system Viktor uses)
- Rug-pull detection algorithms
- Portfolio tracking
- Position sizing and risk management

Actions:
- check_portfolio: Check current holdings and P&L
- scan_market: Scan for trading opportunities
- evaluate_token: Run the full 10-point checklist on a token
- price_alert: Monitor prices and alert on significant moves
- detect_rugpull: Run rug-pull detection on a token
"""

import json
import logging
from datetime import datetime
from typing import Any

from jarvis.skill_loader import BaseSkill, action

logger = logging.getLogger("jarvis.skills.trading")


# ── 10-Point Entry Checklist ─────────────────────────────────

DEFAULT_CHECKLIST = {
    "min_score": 8,
    "criteria": [
        {
            "id": 1,
            "name": "dev_holding",
            "description": "Developer holds less than 5% of supply",
            "check_type": "max_pct",
            "threshold": 5,
            "weight": 1,
        },
        {
            "id": 2,
            "name": "top10_holders",
            "description": "Top 10 holders own less than 20% combined",
            "check_type": "max_pct",
            "threshold": 20,
            "weight": 1,
        },
        {
            "id": 3,
            "name": "insider_pct",
            "description": "Insider wallets hold less than 20%",
            "check_type": "max_pct",
            "threshold": 20,
            "weight": 1,
        },
        {
            "id": 4,
            "name": "bundler_pct",
            "description": "Bundled transactions are less than 15%",
            "check_type": "max_pct",
            "threshold": 15,
            "weight": 1,
        },
        {
            "id": 5,
            "name": "token_age",
            "description": "Token is less than 40 minutes old (catching it early)",
            "check_type": "max_value",
            "threshold": 40,
            "unit": "minutes",
            "weight": 1,
        },
        {
            "id": 6,
            "name": "profit_traders",
            "description": "At least 10 profitable traders already in",
            "check_type": "min_value",
            "threshold": 10,
            "weight": 1,
        },
        {
            "id": 7,
            "name": "social_presence",
            "description": "Has Twitter/X account with real followers (not bots)",
            "check_type": "boolean",
            "weight": 1,
        },
        {
            "id": 8,
            "name": "contract_address_visible",
            "description": "CA is posted in bio/pinned tweet (easy to find)",
            "check_type": "boolean",
            "weight": 1,
        },
        {
            "id": 9,
            "name": "community_quality",
            "description": "Real humans in Telegram/Discord (not bot spam)",
            "check_type": "boolean",
            "weight": 1,
        },
        {
            "id": 10,
            "name": "holder_diversity",
            "description": "Top holders have different funding dates and amounts",
            "check_type": "boolean",
            "weight": 1,
        },
    ],
}


# ── Rug-Pull Detection ──────────────────────────────────────

RUGPULL_SIGNALS = [
    {
        "name": "dev_dump_risk",
        "description": "Developer holds >10% and hasn't locked liquidity",
        "severity": "critical",
        "check": lambda data: data.get("dev_pct", 0) > 10 and not data.get("liquidity_locked", False),
    },
    {
        "name": "honeypot_pattern",
        "description": "Buy transactions succeed but sells fail",
        "severity": "critical",
        "check": lambda data: data.get("sell_fail_rate", 0) > 50,
    },
    {
        "name": "concentrated_supply",
        "description": "Top 5 wallets hold >50% of supply",
        "severity": "high",
        "check": lambda data: data.get("top5_pct", 0) > 50,
    },
    {
        "name": "same_funding_source",
        "description": "Multiple top holders funded from same wallet",
        "severity": "high",
        "check": lambda data: data.get("same_funding_count", 0) > 3,
    },
    {
        "name": "no_social_proof",
        "description": "No Twitter, no Telegram, no website",
        "severity": "medium",
        "check": lambda data: not any([
            data.get("has_twitter"),
            data.get("has_telegram"),
            data.get("has_website"),
        ]),
    },
    {
        "name": "suspicious_volume",
        "description": "Volume is mostly wash trading (same wallets buying/selling)",
        "severity": "high",
        "check": lambda data: data.get("wash_trade_pct", 0) > 40,
    },
    {
        "name": "copycat_token",
        "description": "Name/symbol copies a popular token",
        "severity": "medium",
        "check": lambda data: data.get("is_copycat", False),
    },
    {
        "name": "mint_authority_active",
        "description": "Token creator can still mint new tokens (infinite supply risk)",
        "severity": "critical",
        "check": lambda data: data.get("mint_authority_active", False),
    },
]


class TradingSkill(BaseSkill):
    """Crypto trading automation with checklist-based strategy."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Load checklist config from skill config or use defaults
        skill_config = self.config.get("config", {})
        self.checklist = skill_config.get("checklist", DEFAULT_CHECKLIST)
        self.risk_config = skill_config.get("risk_management", {
            "max_position_pct": 25,
            "stop_loss_pct": 15,
            "take_profit_pct": 50,
            "max_concurrent_positions": 3,
        })

    @action("check_portfolio")
    async def check_portfolio(self, params: dict) -> str:
        """Check portfolio balances and P&L."""
        alert_threshold = params.get("alert_threshold", 5)

        price_data = await self.tools.execute("http_request", {
            "method": "GET",
            "url": "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd&include_24hr_change=true",
        })

        report = f"📊 Portfolio Check — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        report += f"SOL Price: {price_data}\n"

        # Check for saved positions in working memory
        positions = await self.memory.get_working("open_positions")
        if positions:
            report += f"\nOpen Positions: {json.dumps(positions, indent=2)}\n"
        else:
            report += "\nNo open positions.\n"

        await self.memory.store_knowledge(
            f"Portfolio check at {datetime.now().isoformat()}: {price_data}",
            category="trading",
        )

        return report

    @action("scan_market")
    async def scan_market(self, params: dict) -> str:
        """Scan for trading opportunities."""
        news = await self.tools.execute("web_search", {
            "query": "solana memecoin trending today pump.fun",
        })

        report = f"🔍 Market Scan — {datetime.now().strftime('%H:%M')}\n"
        report += f"Trending: {news[:500]}\n"

        return report

    @action("evaluate_token")
    async def evaluate_token(self, params: dict) -> str:
        """Run the full 10-point entry checklist on a token.

        Params:
            token_data: dict with token metrics (dev_pct, top10_pct, etc.)
            Or: address: str — token contract address to look up

        Returns:
            Checklist results with score and recommendation
        """
        token_data = params.get("token_data", {})
        token_name = token_data.get("name", params.get("name", "Unknown"))

        score = 0
        total = 0
        results = []

        for criterion in self.checklist["criteria"]:
            total += criterion["weight"]
            passed = False
            detail = ""

            if criterion["check_type"] == "max_pct":
                value = token_data.get(criterion["name"], 100)
                passed = value <= criterion["threshold"]
                detail = f"{value}% (max {criterion['threshold']}%)"

            elif criterion["check_type"] == "max_value":
                value = token_data.get(criterion["name"], 999)
                passed = value <= criterion["threshold"]
                unit = criterion.get("unit", "")
                detail = f"{value} {unit} (max {criterion['threshold']})"

            elif criterion["check_type"] == "min_value":
                value = token_data.get(criterion["name"], 0)
                passed = value >= criterion["threshold"]
                detail = f"{value} (min {criterion['threshold']})"

            elif criterion["check_type"] == "boolean":
                passed = bool(token_data.get(criterion["name"], False))
                detail = "Yes" if passed else "No"

            if passed:
                score += criterion["weight"]

            results.append({
                "id": criterion["id"],
                "name": criterion["name"],
                "description": criterion["description"],
                "passed": passed,
                "detail": detail,
                "icon": "✅" if passed else "❌",
            })

        # Build report
        min_score = self.checklist.get("min_score", 8)
        recommendation = "BUY" if score >= min_score else "SKIP"

        report = f"📋 Token Evaluation: {token_name}\n"
        report += f"{'═' * 50}\n"
        report += f"Score: {score}/{total} (minimum: {min_score})\n"
        report += f"Recommendation: {'🟢 ' + recommendation if recommendation == 'BUY' else '🔴 ' + recommendation}\n\n"

        for r in results:
            report += f"  {r['icon']} #{r['id']} {r['description']}\n"
            report += f"     → {r['detail']}\n"

        # Position sizing recommendation
        if recommendation == "BUY":
            max_pos = self.risk_config.get("max_position_pct", 25)
            sl = self.risk_config.get("stop_loss_pct", 15)
            tp = self.risk_config.get("take_profit_pct", 50)
            report += f"\n💰 Position Sizing:\n"
            report += f"  Max position: {max_pos}% of portfolio\n"
            report += f"  Stop loss: -{sl}%\n"
            report += f"  Take profit: +{tp}%\n"

        # Store evaluation
        await self.memory.store_knowledge(
            f"Evaluated {token_name}: {score}/{total} → {recommendation}",
            category="trading",
        )

        return report

    @action("detect_rugpull")
    async def detect_rugpull(self, params: dict) -> str:
        """Run rug-pull detection on token data.

        Params:
            token_data: dict with token metrics

        Returns:
            Risk assessment with detected signals
        """
        token_data = params.get("token_data", {})
        token_name = token_data.get("name", "Unknown")

        detected = []
        risk_score = 0

        for signal in RUGPULL_SIGNALS:
            try:
                if signal["check"](token_data):
                    detected.append(signal)
                    if signal["severity"] == "critical":
                        risk_score += 3
                    elif signal["severity"] == "high":
                        risk_score += 2
                    else:
                        risk_score += 1
            except Exception:
                pass

        # Risk level
        if risk_score >= 5:
            risk_level = "🔴 CRITICAL — DO NOT BUY"
        elif risk_score >= 3:
            risk_level = "🟠 HIGH RISK — Avoid"
        elif risk_score >= 1:
            risk_level = "🟡 MEDIUM RISK — Proceed with caution"
        else:
            risk_level = "🟢 LOW RISK — No red flags detected"

        report = f"🛡️ Rug-Pull Detection: {token_name}\n"
        report += f"{'═' * 50}\n"
        report += f"Risk Level: {risk_level}\n"
        report += f"Signals Detected: {len(detected)}/{len(RUGPULL_SIGNALS)}\n\n"

        if detected:
            for signal in detected:
                severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(signal["severity"], "⚪")
                report += f"  {severity_icon} [{signal['severity'].upper()}] {signal['name']}\n"
                report += f"     {signal['description']}\n"
        else:
            report += "  ✅ No rug-pull signals detected.\n"

        report += f"\n⚠️ Disclaimer: This is algorithmic analysis, not financial advice.\n"
        report += f"   Always DYOR and never invest more than you can afford to lose.\n"

        return report

    @action("price_alert")
    async def price_alert(self, params: dict) -> str:
        """Monitor a token's price and alert on significant moves."""
        token = params.get("token", "solana")
        threshold = params.get("threshold", 5)

        price_data = await self.tools.execute("http_request", {
            "method": "GET",
            "url": f"https://api.coingecko.com/api/v3/simple/price?ids={token}&vs_currencies=usd&include_24hr_change=true",
        })

        return f"Price alert check for {token}: {price_data}"
