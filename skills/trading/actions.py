"""Trading Skill — crypto portfolio monitoring and market scanning.

Actions:
- check_portfolio: Check current holdings and P&L
- scan_market: Scan for trading opportunities
- price_alert: Monitor prices and alert on significant moves
"""

import logging
from datetime import datetime

from jarvis.skill_loader import BaseSkill, action

logger = logging.getLogger("jarvis.skills.trading")


class TradingSkill(BaseSkill):
    """Crypto trading automation skill."""

    @action("check_portfolio")
    async def check_portfolio(self, params: dict) -> str:
        """Check portfolio balances and P&L."""
        alert_threshold = params.get("alert_threshold", 5)

        # Fetch SOL price
        price_data = await self.tools.execute("http_request", {
            "method": "GET",
            "url": "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd&include_24hr_change=true",
        })

        # Build report
        report = f"📊 Portfolio Check — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        report += f"SOL Price Data: {price_data}\n"

        # Store in memory for trend tracking
        await self.memory.store_knowledge(
            f"Portfolio check at {datetime.now().isoformat()}: {price_data}",
            category="trading",
        )

        return report

    @action("scan_market")
    async def scan_market(self, params: dict) -> str:
        """Scan for trading opportunities using configurable filters."""
        filters = params.get("filters", {})

        # Search for market news
        news = await self.tools.execute("web_search", {
            "query": "solana memecoin trending today pump.fun",
        })

        report = f"🔍 Market Scan — {datetime.now().strftime('%H:%M')}\n"
        report += f"News: {news[:500]}\n"

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
