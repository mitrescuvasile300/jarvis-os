---
name: web-search
description: Search the web for current information using DuckDuckGo.
---

# Web Search Tool

You can search the web in real-time using DuckDuckGo.

## Available Function

- `web_search(query)` — Returns top 5 results with title, snippet, and URL

## When to Use

- User asks about current events, news, prices
- User asks a factual question you're not 100% sure about
- User says "search for...", "find...", "what's the latest on..."
- Any question that might need up-to-date information

## Best Practices

1. Use specific, targeted queries (not full sentences)
2. If search results aren't enough, use `browse` to open promising URLs
3. Always cite sources when reporting search results
4. For deep research, chain: `web_search` → find good URLs → `browse` each one

## Example

User: "what's the latest AI news?"
1. `web_search(query="AI news today 2026")`
2. Summarize top results
3. Optionally: `browse` the most interesting article for details
