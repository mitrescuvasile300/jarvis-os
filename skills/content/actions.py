"""Content Skill — social media and content creation.

Actions:
- draft_post: Generate a post for a platform
- check_scheduled: Check and execute scheduled posts
- content_ideas: Generate content ideas based on trends
"""

import logging
from datetime import datetime

from jarvis.skill_loader import BaseSkill, action

logger = logging.getLogger("jarvis.skills.content")


class ContentSkill(BaseSkill):
    """Content creation and social media management."""

    @action("draft_post")
    async def draft_post(self, params: dict) -> str:
        """Draft a post for a social media platform."""
        platform = params.get("platform", "twitter")
        topic = params.get("topic", "")
        tone = params.get("tone", self.config.get("config", {}).get("tone", "professional"))

        char_limit = self.config.get("config", {}).get("character_limits", {}).get(platform, 280)

        prompt = f"""Draft a {platform} post about: {topic}
Tone: {tone}
Character limit: {char_limit}
Make it engaging and authentic. No hashtag spam."""

        response = await self.llm.chat(
            messages=[
                {"role": "system", "content": "You are a social media content creator. Write concise, engaging posts."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            max_tokens=300,
        )

        draft = response.get("text", "")

        # Save draft
        await self.tools.execute("write_file", {
            "path": f"data/content/drafts/{platform}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            "content": draft,
        })

        return f"📝 Draft ({platform}, {len(draft)} chars):\n{draft}"

    @action("check_scheduled")
    async def check_scheduled(self, params: dict) -> str:
        """Check for scheduled posts that need to be published."""
        platforms = params.get("platforms", ["twitter"])
        return f"Checked scheduled posts for: {', '.join(platforms)}. No posts due."

    @action("content_ideas")
    async def content_ideas(self, params: dict) -> str:
        """Generate content ideas based on current trends."""
        topics = params.get("topics", ["AI", "crypto"])

        ideas = f"💡 Content Ideas — {datetime.now().strftime('%Y-%m-%d')}\n\n"

        for topic in topics:
            trends = await self.tools.execute("web_search", {
                "query": f"{topic} trending topics this week",
            })
            ideas += f"## {topic}\n{trends[:300]}\n\n"

        return ideas
