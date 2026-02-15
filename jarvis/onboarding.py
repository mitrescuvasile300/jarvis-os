"""Jarvis Onboarding — "Know Your Tony Stark" system.

When Jarvis first meets a new user, he should learn everything about them.
Just like the real Jarvis knows Tony Stark's preferences, schedule, allergies,
coffee order, and communication style — our Jarvis does the same.

The onboarding flow:
1. Detects if user-profile.md is mostly empty (first run)
2. Asks a structured series of questions across categories
3. Saves answers directly to knowledge files
4. Adapts tone and behavior based on what it learns

Onboarding categories:
- Identity: Name, role, what they do
- Work: Projects, tools, daily routine
- Communication: Language, formality, notification preferences
- Preferences: Dark/light mode, response length, emoji usage
- Goals: What they want from Jarvis, top priorities
"""

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger("jarvis.onboarding")

# Onboarding questions organized by category
# Each question has: id, category, question text, follow_up (optional)
ONBOARDING_QUESTIONS = [
    # Identity
    {
        "id": "name",
        "category": "identity",
        "question": "First things first — what should I call you?",
        "knowledge_key": "Name",
    },
    {
        "id": "role",
        "category": "identity",
        "question": "What do you do? (role, profession, or however you'd describe yourself)",
        "knowledge_key": "Role/Profession",
    },
    # Work
    {
        "id": "projects",
        "category": "work",
        "question": "What are you currently working on? Any active projects I should know about?",
        "knowledge_key": "Active Projects",
    },
    {
        "id": "tools",
        "category": "work",
        "question": "What tools and platforms do you use daily? (e.g., Slack, GitHub, Notion, specific apps)",
        "knowledge_key": "Daily Tools",
    },
    {
        "id": "routine",
        "category": "work",
        "question": "Walk me through a typical day — when do you start, what's your rhythm, when do you prefer not to be disturbed?",
        "knowledge_key": "Daily Routine",
    },
    # Communication
    {
        "id": "language",
        "category": "communication",
        "question": "What language(s) do you prefer for our conversations?",
        "knowledge_key": "Preferred Language",
    },
    {
        "id": "style",
        "category": "communication",
        "question": "How do you like your information served? (bullet points vs paragraphs, detailed vs concise, formal vs casual)",
        "knowledge_key": "Communication Style",
    },
    # Preferences
    {
        "id": "response_style",
        "category": "preferences",
        "question": "When I help you, do you prefer: short & actionable answers, or thorough explanations with context?",
        "knowledge_key": "Response Preference",
    },
    {
        "id": "interests",
        "category": "preferences",
        "question": "Any personal interests or topics you'd want me to keep an eye on? (tech news, crypto, sports, stocks, etc.)",
        "knowledge_key": "Interests to Monitor",
    },
    # Goals
    {
        "id": "expectations",
        "category": "goals",
        "question": "What's the #1 thing you want me to help you with? What would make me invaluable to you?",
        "knowledge_key": "Primary Goal for Jarvis",
    },
    {
        "id": "pain_points",
        "category": "goals",
        "question": "What's the most repetitive or annoying part of your day that you'd love to automate?",
        "knowledge_key": "Pain Points to Automate",
    },
    {
        "id": "anything_else",
        "category": "goals",
        "question": "Anything else I should know? Quirks, pet peeves, things previous assistants got wrong?",
        "knowledge_key": "Additional Notes",
    },
]


class OnboardingManager:
    """Manages the onboarding flow for new users."""

    def __init__(self, knowledge_manager):
        self.knowledge = knowledge_manager
        self._onboarding_state = None  # Loaded from working memory or None

    def needs_onboarding(self) -> bool:
        """Check if onboarding is needed (user profile is mostly empty)."""
        profile = self.knowledge.get_user_profile()
        if not profile:
            return True

        # Check if profile has actual content (not just templates)
        meaningful_lines = [
            line for line in profile.split("\n")
            if line.strip()
            and not line.startswith("#")
            and not line.startswith("---")
            and not line.startswith("*Auto-updated")
            and "(none yet)" not in line
            and "(not yet observed)" not in line
            and line.strip() != "-"
        ]

        # If fewer than 3 meaningful lines, probably needs onboarding
        return len(meaningful_lines) < 3

    def get_onboarding_state(self, state_data: dict | None = None) -> dict:
        """Get or initialize onboarding state."""
        if state_data:
            return state_data

        return {
            "active": True,
            "current_question_idx": 0,
            "answers": {},
            "completed": False,
        }

    def get_current_question(self, state: dict) -> dict | None:
        """Get the current onboarding question."""
        idx = state.get("current_question_idx", 0)
        if idx >= len(ONBOARDING_QUESTIONS):
            return None
        return ONBOARDING_QUESTIONS[idx]

    def get_intro_message(self) -> str:
        """Get the onboarding introduction message."""
        return (
            "👋 Welcome! I'm Jarvis, your personal AI operating system.\n\n"
            "Before we start working together, I'd like to get to know you — "
            "just like the real Jarvis knows everything about Tony Stark. "
            "I'll ask you a few questions so I can personalize everything to your style.\n\n"
            "You can skip any question by saying 'skip', and come back to it later.\n\n"
            "Ready? Let's start!\n\n"
            f"**Question 1/{len(ONBOARDING_QUESTIONS)}**: {ONBOARDING_QUESTIONS[0]['question']}"
        )

    def process_answer(self, state: dict, answer: str) -> tuple[dict, str | None]:
        """Process an answer and return updated state + next message.

        Returns:
            (updated_state, next_message_or_None_if_complete)
        """
        idx = state["current_question_idx"]
        question = ONBOARDING_QUESTIONS[idx]

        # Store answer (unless skipped)
        if answer.strip().lower() not in ("skip", "treci", "sari"):
            state["answers"][question["id"]] = {
                "question": question["question"],
                "answer": answer,
                "knowledge_key": question["knowledge_key"],
                "category": question["category"],
            }

        # Move to next question
        state["current_question_idx"] = idx + 1

        if state["current_question_idx"] >= len(ONBOARDING_QUESTIONS):
            state["completed"] = True
            state["active"] = False
            return state, None

        # Build next question message
        next_q = ONBOARDING_QUESTIONS[state["current_question_idx"]]
        q_num = state["current_question_idx"] + 1
        total = len(ONBOARDING_QUESTIONS)

        # Add a small acknowledgment of their answer
        next_msg = f"**Question {q_num}/{total}**: {next_q['question']}"

        return state, next_msg

    def build_profile_from_answers(self, answers: dict) -> str:
        """Build a formatted user profile from onboarding answers."""
        sections = {
            "identity": [],
            "work": [],
            "communication": [],
            "preferences": [],
            "goals": [],
        }

        for qid, data in answers.items():
            category = data["category"]
            key = data["knowledge_key"]
            answer = data["answer"]
            if category in sections:
                sections[category].append(f"- **{key}**: {answer}")

        parts = ["# User Profile\n"]

        if sections["identity"]:
            parts.append("## Identity")
            parts.extend(sections["identity"])
            parts.append("")

        if sections["work"]:
            parts.append("## Work")
            parts.extend(sections["work"])
            parts.append("")

        if sections["communication"]:
            parts.append("## Communication")
            parts.extend(sections["communication"])
            parts.append("")

        if sections["preferences"]:
            parts.append("## Preferences")
            parts.extend(sections["preferences"])
            parts.append("")

        if sections["goals"]:
            parts.append("## Goals & Priorities")
            parts.extend(sections["goals"])
            parts.append("")

        parts.append("---")
        parts.append("*Profile built during onboarding. Auto-updated by Jarvis after conversations.*")

        return "\n".join(parts)

    def get_completion_message(self, answers: dict) -> str:
        """Generate a personalized completion message."""
        name = answers.get("name", {}).get("answer", "boss")
        num_answered = len(answers)

        return (
            f"✅ Got it, {name}! Onboarding complete — I learned {num_answered} things about you.\n\n"
            "Your profile is saved and I'll use it in every conversation. "
            "The more we work together, the better I'll get.\n\n"
            "What can I help you with first?"
        )

    async def save_profile(self, state: dict):
        """Save the onboarding answers to knowledge files."""
        answers = state.get("answers", {})
        if not answers:
            return

        # Build and save user profile
        profile_content = self.build_profile_from_answers(answers)
        profile_path = self.knowledge.knowledge_dir / "user-profile.md"
        profile_path.write_text(profile_content, encoding="utf-8")
        self.knowledge._cache["user-profile.md"] = profile_content

        # Update context with projects if mentioned
        projects_answer = answers.get("projects", {}).get("answer", "")
        if projects_answer:
            await self.knowledge._append_to_file(
                "context.md",
                [f"Active projects (from onboarding): {projects_answer}"]
            )

        logger.info(f"Onboarding profile saved: {len(answers)} answers")
