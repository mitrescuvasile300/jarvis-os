"""Skill Loader — discovers and loads skill modules.

Skills live in:
- skills/ (built-in)
- skills-custom/ (user-defined, mounted via Docker volume)
"""

import importlib.util
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("jarvis.skills")


class BaseSkill:
    """Base class for all Jarvis skills."""

    def __init__(self, name: str, config: dict, tools, llm, memory):
        self.name = name
        self.config = config
        self.description = config.get("description", "")
        self.enabled = True
        self.tools = tools
        self.llm = llm
        self.memory = memory
        self.actions: dict[str, Any] = {}

    async def execute(self, action: str, params: dict) -> Any:
        """Execute a skill action."""
        if action not in self.actions:
            raise KeyError(f"Action '{action}' not found in skill '{self.name}'")
        handler = self.actions[action]
        return await handler(params)

    async def notify(self, message: str):
        """Send a notification (via configured integration)."""
        logger.info(f"[{self.name}] Notification: {message}")


def action(name: str):
    """Decorator to mark a method as a skill action."""
    def decorator(func):
        func._action_name = name
        return func
    return decorator


class SkillLoader:
    def __init__(self, config: dict, tools, llm, memory):
        self.config = config
        self.tools = tools
        self.llm = llm
        self.memory = memory
        self.enabled_skills = config.get("enabled", [])

    async def load_all(self) -> dict[str, BaseSkill]:
        """Discover and load all skills."""
        skills = {}

        # Load from built-in skills/
        skills.update(await self._load_from_dir(Path("skills")))

        # Load from custom skills (Docker volume mount)
        custom_path = Path("skills-custom")
        if custom_path.exists():
            skills.update(await self._load_from_dir(custom_path))

        # Load community skills (ClawHub etc)
        community_path = Path("skills-community")
        if community_path.exists():
            skills.update(await self._load_from_dir(community_path))

        # Filter to enabled only (if specified)
        if self.enabled_skills:
            skills = {k: v for k, v in skills.items() if k in self.enabled_skills}

        return skills

    async def _load_from_dir(self, base_path: Path) -> dict[str, BaseSkill]:
        """Load skills from a directory."""
        skills = {}

        if not base_path.exists():
            return skills

        for skill_dir in sorted(base_path.iterdir()):
            if not skill_dir.is_dir():
                continue

            # Check for SKILL.yml
            skill_yml = skill_dir / "SKILL.yml"
            if not skill_yml.exists():
                continue

            try:
                config = yaml.safe_load(skill_yml.read_text()) or {}
                name = config.get("name", skill_dir.name)

                # Try to load actions.py
                actions_file = skill_dir / "actions.py"
                if actions_file.exists():
                    skill = await self._load_python_skill(name, config, actions_file)
                else:
                    skill = BaseSkill(name, config, self.tools, self.llm, self.memory)

                skills[name] = skill
                logger.info(f"Loaded skill: {name} ({len(skill.actions)} actions)")

            except Exception as e:
                logger.error(f"Failed to load skill from {skill_dir}: {e}")

        return skills

    async def _load_python_skill(self, name: str, config: dict, actions_file: Path) -> BaseSkill:
        """Load a skill with Python actions."""
        spec = importlib.util.spec_from_file_location(f"skill_{name}", str(actions_file))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find the skill class (subclass of BaseSkill)
        skill_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, BaseSkill) and attr is not BaseSkill:
                skill_class = attr
                break

        if skill_class:
            skill = skill_class(name, config, self.tools, self.llm, self.memory)
            # Register decorated actions
            for method_name in dir(skill):
                method = getattr(skill, method_name)
                if callable(method) and hasattr(method, "_action_name"):
                    skill.actions[method._action_name] = method
        else:
            skill = BaseSkill(name, config, self.tools, self.llm, self.memory)
            # Register module-level async functions as actions
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if callable(attr) and hasattr(attr, "_action_name"):
                    skill.actions[attr._action_name] = attr

        return skill
