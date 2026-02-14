"""Standalone health check script — monitors Jarvis and reports issues."""

import httpx
import sys
import time
from datetime import datetime


def check_health(url: str = "http://localhost:8080") -> dict:
    """Check Jarvis health and return status."""
    try:
        response = httpx.get(f"{url}/health", timeout=10.0)
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "healthy",
                "agent": data.get("agent", "unknown"),
                "uptime": data.get("uptime_seconds", 0),
                "memory": data.get("memory_entries", 0),
                "skills": data.get("skills_loaded", 0),
            }
        else:
            return {"status": "unhealthy", "error": f"HTTP {response.status_code}"}
    except httpx.ConnectError:
        return {"status": "down", "error": "Cannot connect to Jarvis"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    result = check_health(url)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if result["status"] == "healthy":
        print(f"[{now}] ✅ {result['agent']} is healthy")
        print(f"  Uptime: {result['uptime']}s | Memory: {result['memory']} | Skills: {result['skills']}")
        sys.exit(0)
    else:
        print(f"[{now}] ❌ Jarvis is {result['status']}: {result.get('error', 'unknown')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
