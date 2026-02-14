"""Code Skill — code generation, review, and maintenance.

Actions:
- generate: Write code based on a description
- review: Review code for issues and improvements
- debug: Help debug an error
- memory_cleanup: System maintenance task
"""

import logging
from datetime import datetime

from jarvis.skill_loader import BaseSkill, action

logger = logging.getLogger("jarvis.skills.code")


class CodeSkill(BaseSkill):
    """Code generation and system maintenance."""

    @action("generate")
    async def generate(self, params: dict) -> str:
        """Generate code from a description."""
        description = params.get("description", "")
        language = params.get("language", "python")

        if not description:
            return "Error: 'description' parameter is required"

        response = await self.llm.chat(
            messages=[
                {
                    "role": "system",
                    "content": f"You are an expert {language} programmer. Write clean, well-documented code. Include error handling and type hints.",
                },
                {"role": "user", "content": f"Write {language} code for: {description}"},
            ],
            temperature=0.3,
            max_tokens=4096,
        )

        code = response.get("text", "")

        # Save to file
        ext = {"python": "py", "javascript": "js", "typescript": "ts"}.get(language, language)
        filename = f"data/generated/{datetime.now().strftime('%Y%m%d_%H%M')}.{ext}"
        await self.tools.execute("write_file", {"path": filename, "content": code})

        return f"Generated {language} code:\n{code}"

    @action("review")
    async def review(self, params: dict) -> str:
        """Review code for issues."""
        file_path = params.get("file", "")
        if not file_path:
            return "Error: 'file' parameter is required"

        code = await self.tools.execute("read_file", {"path": file_path})

        response = await self.llm.chat(
            messages=[
                {
                    "role": "system",
                    "content": "You are a senior code reviewer. Focus on: bugs, security issues, performance, readability, and best practices.",
                },
                {"role": "user", "content": f"Review this code:\n\n{code}"},
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        return f"Code Review for {file_path}:\n{response.get('text', '')}"

    @action("memory_cleanup")
    async def memory_cleanup(self, params: dict) -> str:
        """System maintenance — clean up old memory entries."""
        await self.memory.cleanup()
        count = await self.memory.count()
        return f"Memory cleanup complete. {count} entries remaining."
