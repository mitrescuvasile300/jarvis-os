---
name: browser
description: Browse websites, take screenshots, click elements, fill forms using Playwright Chromium.
---

# Browser Tools

You have a real headless Chromium browser. Use it whenever the user asks to visit, check, or interact with a website.

## Available Functions

- `browse(url, extract, wait_for)` — Navigate to URL, get page content
  - extract: "text" (default), "markdown" (structured), "html" (raw)
  - wait_for: "domcontentloaded" (fast), "networkidle" (wait for all requests)
- `screenshot(url, full_page)` — Take a PNG screenshot
  - Returns path to saved image file
  - full_page=true captures entire scrollable page
- `click(selector)` — Click an element by CSS selector
- `fill_form(selector, value)` — Type into a form field
- `page_info()` — Get current page's links, buttons, and form fields

## When to Use

- User says "open/check/visit [site]" → `browse`
- User says "screenshot [site]" → `screenshot`
- User asks about a website's content → `browse` with extract="markdown"
- User wants to fill a form or log in → `page_info` first, then `fill_form` + `click`

## Best Practices

1. Use `browse` first to understand the page, then `click`/`fill_form` if needed
2. Use `page_info` before clicking to discover available selectors
3. Set `wait_for="networkidle"` for JavaScript-heavy sites (SPAs)
4. Screenshots are saved to `/api/uploads/` and can be shown in chat

## Example Flow

User: "check e-meniu.ro and tell me what it sells"
1. `browse(url="https://e-meniu.ro", extract="markdown")`
2. Read the content
3. Summarize for the user

User: "screenshot google.com"
1. `screenshot(url="https://google.com")`
2. Return the screenshot path
