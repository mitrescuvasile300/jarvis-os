"""Browser Tool — Playwright-based web browsing for Jarvis.

Provides headless browser automation:
- Navigate to URLs and extract page content
- Take screenshots
- Click elements, fill forms
- Execute JavaScript
- Extract structured data from pages

The browser is lazily initialized and reused across calls.
"""

import asyncio
import base64
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.browser")

# Singleton browser instance
_browser = None
_page = None


async def _get_page():
    """Get or create a browser page (lazy initialization)."""
    global _browser, _page

    if _page and not _page.is_closed():
        return _page

    try:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        _browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-setuid-sandbox",
            ],
        )
        context = await _browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        _page = await context.new_page()
        logger.info("Browser initialized (Chromium headless)")
        return _page

    except ImportError:
        raise RuntimeError("Playwright not installed — pip install playwright && playwright install chromium")
    except Exception as e:
        logger.error(f"Browser init failed: {e}")
        raise


async def tool_browse(args: dict) -> str:
    """Navigate to a URL and extract page content."""
    url = args["url"]
    wait_for = args.get("wait_for", "domcontentloaded")  # or "networkidle", "load"
    extract = args.get("extract", "text")  # "text", "html", "markdown"

    try:
        page = await _get_page()
        response = await page.goto(url, wait_until=wait_for, timeout=30000)

        status = response.status if response else "unknown"
        title = await page.title()

        if extract == "html":
            content = await page.content()
            if len(content) > 15000:
                content = content[:15000] + "\n... (truncated)"
        elif extract == "markdown":
            # Extract readable text with structure
            content = await page.evaluate("""() => {
                function extractText(node, depth = 0) {
                    let result = '';
                    for (const child of node.childNodes) {
                        if (child.nodeType === 3) {
                            const text = child.textContent.trim();
                            if (text) result += text + ' ';
                        } else if (child.nodeType === 1) {
                            const tag = child.tagName.toLowerCase();
                            if (['script', 'style', 'noscript', 'svg'].includes(tag)) continue;
                            if (['h1','h2','h3','h4','h5','h6'].includes(tag)) {
                                const level = '#'.repeat(parseInt(tag[1]));
                                result += '\\n' + level + ' ' + child.textContent.trim() + '\\n';
                            } else if (tag === 'p' || tag === 'div') {
                                result += '\\n' + extractText(child, depth + 1) + '\\n';
                            } else if (tag === 'li') {
                                result += '\\n- ' + child.textContent.trim();
                            } else if (tag === 'a') {
                                const href = child.getAttribute('href') || '';
                                result += '[' + child.textContent.trim() + '](' + href + ')';
                            } else if (tag === 'br') {
                                result += '\\n';
                            } else {
                                result += extractText(child, depth + 1);
                            }
                        }
                    }
                    return result;
                }
                return extractText(document.body).replace(/\\n{3,}/g, '\\n\\n').trim();
            }""")
            if len(content) > 15000:
                content = content[:15000] + "\n... (truncated)"
        else:
            # Plain text extraction
            content = await page.evaluate("""() => {
                const el = document.body;
                const scripts = el.querySelectorAll('script, style, noscript, svg');
                scripts.forEach(s => s.remove());
                return el.innerText.trim();
            }""")
            if len(content) > 15000:
                content = content[:15000] + "\n... (truncated)"

        return f"**{title}** (HTTP {status})\nURL: {url}\n\n{content}"

    except Exception as e:
        return f"Browser error: {e}"


async def tool_screenshot(args: dict) -> str:
    """Take a screenshot of the current page or a URL."""
    url = args.get("url")
    full_page = args.get("full_page", False)

    try:
        page = await _get_page()

        if url:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(1)  # Let rendering settle

        # Save screenshot
        screenshots_dir = Path("data/uploads")
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        import uuid
        filename = f"screenshot_{uuid.uuid4().hex[:8]}.png"
        filepath = screenshots_dir / filename

        await page.screenshot(path=str(filepath), full_page=full_page)

        title = await page.title()
        current_url = page.url

        return (
            f"Screenshot saved: /api/uploads/{filename}\n"
            f"Page: {title}\n"
            f"URL: {current_url}\n"
            f"Size: {filepath.stat().st_size:,} bytes"
        )

    except Exception as e:
        return f"Screenshot error: {e}"


async def tool_click(args: dict) -> str:
    """Click an element on the page."""
    selector = args["selector"]

    try:
        page = await _get_page()
        await page.click(selector, timeout=10000)
        await asyncio.sleep(0.5)  # Wait for navigation/rendering

        title = await page.title()
        url = page.url
        return f"Clicked: {selector}\nNow on: {title} ({url})"

    except Exception as e:
        return f"Click error on '{selector}': {e}"


async def tool_fill(args: dict) -> str:
    """Fill a form field."""
    selector = args["selector"]
    value = args["value"]

    try:
        page = await _get_page()
        await page.fill(selector, value, timeout=10000)
        return f"Filled '{selector}' with '{value[:50]}...'" if len(value) > 50 else f"Filled '{selector}' with '{value}'"

    except Exception as e:
        return f"Fill error on '{selector}': {e}"


async def tool_page_info(args: dict) -> str:
    """Get current page info and interactive elements."""
    try:
        page = await _get_page()

        info = await page.evaluate("""() => {
            const links = Array.from(document.querySelectorAll('a[href]')).slice(0, 20).map(a => ({
                text: a.textContent.trim().substring(0, 60),
                href: a.href
            })).filter(a => a.text);

            const buttons = Array.from(document.querySelectorAll('button, input[type="submit"]')).slice(0, 10).map(b => ({
                text: (b.textContent || b.value || '').trim().substring(0, 60),
                type: b.tagName.toLowerCase()
            })).filter(b => b.text);

            const inputs = Array.from(document.querySelectorAll('input, textarea, select')).slice(0, 10).map(i => ({
                name: i.name || i.id || '',
                type: i.type || i.tagName.toLowerCase(),
                placeholder: i.placeholder || ''
            })).filter(i => i.name);

            return {
                title: document.title,
                url: window.location.href,
                links: links,
                buttons: buttons,
                inputs: inputs
            };
        }""")

        parts = [f"**{info['title']}**\nURL: {info['url']}\n"]

        if info['links']:
            parts.append("**Links:**")
            for link in info['links']:
                parts.append(f"  - [{link['text']}]({link['href']})")

        if info['buttons']:
            parts.append("\n**Buttons:**")
            for btn in info['buttons']:
                parts.append(f"  - {btn['type']}: \"{btn['text']}\"")

        if info['inputs']:
            parts.append("\n**Form fields:**")
            for inp in info['inputs']:
                parts.append(f"  - {inp['name']} ({inp['type']})" +
                             (f" placeholder: \"{inp['placeholder']}\"" if inp['placeholder'] else ""))

        return "\n".join(parts)

    except Exception as e:
        return f"Page info error: {e}"


def register_browser_tools(registry):
    """Register all browser tools with the tool registry."""

    registry.register(
        name="browse",
        description=(
            "Navigate to a URL and extract the page content as text. "
            "Use for reading articles, checking websites, research. "
            "Set extract='markdown' for structured output, 'html' for raw HTML."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to navigate to"},
                "extract": {
                    "type": "string",
                    "enum": ["text", "markdown", "html"],
                    "description": "Content extraction format (default: text)",
                },
                "wait_for": {
                    "type": "string",
                    "enum": ["domcontentloaded", "load", "networkidle"],
                    "description": "When to consider page loaded (default: domcontentloaded)",
                },
            },
            "required": ["url"],
        },
        handler=tool_browse,
    )

    registry.register(
        name="screenshot",
        description=(
            "Take a screenshot of the current page or navigate to a URL first. "
            "Returns the path to the saved screenshot image."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Optional URL to navigate to first"},
                "full_page": {"type": "boolean", "description": "Capture full scrollable page (default: false)"},
            },
        },
        handler=tool_screenshot,
    )

    registry.register(
        name="click",
        description="Click an element on the current page using a CSS selector.",
        parameters={
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector of element to click (e.g., 'button.submit', '#login-btn')"},
            },
            "required": ["selector"],
        },
        handler=tool_click,
    )

    registry.register(
        name="fill_form",
        description="Fill a form field on the current page.",
        parameters={
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector of the input field"},
                "value": {"type": "string", "description": "Value to type into the field"},
            },
            "required": ["selector", "value"],
        },
        handler=tool_fill,
    )

    registry.register(
        name="page_info",
        description=(
            "Get info about the current page: title, URL, links, buttons, and form fields. "
            "Use to understand what's on the page before clicking or filling forms."
        ),
        parameters={
            "type": "object",
            "properties": {},
        },
        handler=tool_page_info,
    )

    logger.info("Browser tools registered: browse, screenshot, click, fill_form, page_info")
