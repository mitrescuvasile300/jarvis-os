"""Example plugin: Weather lookup.

This shows how to create a plugin tool for Jarvis OS.
Drop .py files in the plugins/ folder and they're auto-loaded.
"""

from jarvis.plugins import plugin_tool


@plugin_tool(
    name="get_weather",
    description="Get current weather for a city. Returns temperature and conditions.",
    parameters={"city": "Name of the city (e.g., 'London', 'New York')"},
)
async def get_weather(city: str) -> str:
    """Fetch weather from wttr.in (no API key needed)."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://wttr.in/{city}?format=3")
            if resp.status_code == 200:
                return resp.text.strip()
            return f"Could not get weather for {city} (status {resp.status_code})"
    except Exception as e:
        return f"Weather lookup failed: {e}"


@plugin_tool(
    name="get_crypto_price",
    description="Get the current price of a cryptocurrency in USD.",
    parameters={"symbol": "Crypto symbol (e.g., 'bitcoin', 'solana', 'ethereum')"},
)
async def get_crypto_price(symbol: str) -> str:
    """Fetch crypto price from CoinGecko (no API key needed)."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.coingecko.com/api/v3/simple/price",
                params={"ids": symbol.lower(), "vs_currencies": "usd", "include_24hr_change": "true"},
            )
            data = resp.json()
            if symbol.lower() in data:
                info = data[symbol.lower()]
                price = info.get("usd", "?")
                change = info.get("usd_24h_change", 0)
                arrow = "📈" if change >= 0 else "📉"
                return f"{symbol.upper()}: ${price:,.2f} {arrow} {change:+.1f}% (24h)"
            return f"Unknown cryptocurrency: {symbol}"
    except Exception as e:
        return f"Price lookup failed: {e}"
