"""Research Skill — web research and daily briefings.

Actions:
- daily_briefing: Generate a morning briefing on configured topics
- deep_research: In-depth research on a specific topic
- monitor_topic: Track a topic over time
"""

import logging
from datetime import datetime

from jarvis.skill_loader import BaseSkill, action

logger = logging.getLogger("jarvis.skills.research")


class ResearchSkill(BaseSkill):
    """Web research and monitoring skill."""

    @action("daily_briefing")
    async def daily_briefing(self, params: dict) -> str:
        """Generate a daily briefing on configured topics."""
        topics = params.get("topics", self.config.get("config", {}).get("default_topics", ["AI", "crypto"]))
        max_articles = params.get("max_articles", 10)

        briefing = f"📰 Daily Briefing — {datetime.now().strftime('%A, %B %d %Y')}\n\n"

        for topic in topics:
            # Search for recent news
            results = await self.tools.execute("web_search", {
                "query": f"{topic} news today {datetime.now().strftime('%Y-%m-%d')}",
            })

            briefing += f"## {topic.title()}\n{results[:500]}\n\n"

        # Store briefing
        await self.memory.store_knowledge(
            f"Daily briefing generated on {datetime.now().isoformat()} for topics: {', '.join(topics)}",
            category="research",
        )

        return briefing

    @action("deep_research")
    async def deep_research(self, params: dict) -> str:
        """Conduct in-depth research on a topic."""
        topic = params.get("topic", "")
        if not topic:
            return "Error: 'topic' parameter is required"

        # Multiple search angles
        queries = [
            f"{topic} overview",
            f"{topic} latest developments 2025 2026",
            f"{topic} analysis expert opinion",
        ]

        research = f"🔬 Deep Research: {topic}\n\n"

        for query in queries:
            results = await self.tools.execute("web_search", {"query": query})
            research += f"### {query}\n{results[:500]}\n\n"

        # Store research
        await self.memory.store_knowledge(
            f"Deep research on '{topic}' completed on {datetime.now().isoformat()}",
            category="research",
        )

        # Save to file
        filename = f"data/research/{topic.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.md"
        await self.tools.execute("write_file", {"path": filename, "content": research})

        return research

    @action("monitor_topic")
    async def monitor_topic(self, params: dict) -> str:
        """Track a topic over time, alert on new developments."""
        topic = params.get("topic", "")
        results = await self.tools.execute("web_search", {"query": f"{topic} breaking news"})
        return f"Monitor update for '{topic}': {results[:300]}"
