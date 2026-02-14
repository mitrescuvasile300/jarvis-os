# 🔌 Jarvis OS Plugins

Drop Python files in this directory to add custom tools to your agent.

## How It Works

1. Create a `.py` file in this folder
2. Use the `@plugin_tool` decorator to register functions
3. Restart Jarvis — your tools are automatically available

## Example: Weather Plugin

```python
# plugins/weather.py
from jarvis.plugins import plugin_tool

@plugin_tool(
    name="get_weather",
    description="Get current weather for a city",
    parameters={"city": "Name of the city"}
)
async def get_weather(city: str) -> str:
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://wttr.in/{city}?format=3")
        return resp.text
```

## Example: Database Query Plugin

```python
# plugins/database.py
from jarvis.plugins import plugin_tool

@plugin_tool(
    name="query_db",
    description="Run a SQL query on the database",
    parameters={"query": "SQL query to execute"}
)
def query_db(query: str) -> str:
    import sqlite3
    conn = sqlite3.connect("data/app.db")
    cursor = conn.execute(query)
    results = cursor.fetchall()
    conn.close()
    return str(results)
```

## Example: Notification Plugin

```python
# plugins/notify.py
from jarvis.plugins import plugin_tool

@plugin_tool(
    name="send_notification",
    description="Send a push notification via ntfy.sh",
    parameters={
        "topic": "ntfy.sh topic name",
        "message": "Notification message"
    }
)
async def send_notification(topic: str, message: str) -> str:
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://ntfy.sh/{topic}",
            content=message,
            headers={"Title": "Jarvis OS"}
        )
        return f"Sent: {resp.status_code}"
```

## Rules

- File must be a `.py` file (not starting with `_`)
- Use `@plugin_tool` decorator from `jarvis.plugins`
- Functions can be `async` or regular
- Parameters are passed as keyword arguments
- Return value should be a string (the agent sees this)
