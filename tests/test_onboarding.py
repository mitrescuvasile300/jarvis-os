"""Tests for the Onboarding system."""

import pytest
import pytest_asyncio
from pathlib import Path

from jarvis.knowledge_manager import KnowledgeManager
from jarvis.onboarding import OnboardingManager, ONBOARDING_QUESTIONS


@pytest_asyncio.fixture
async def knowledge(tmp_path):
    km = KnowledgeManager(config={}, knowledge_dir=str(tmp_path / "knowledge"))
    await km.initialize()
    return km


@pytest.fixture
def onboarding(knowledge):
    return OnboardingManager(knowledge)


class TestNeedsOnboarding:
    def test_needs_onboarding_on_fresh_install(self, onboarding):
        assert onboarding.needs_onboarding() is True

    @pytest.mark.asyncio
    async def test_no_onboarding_after_profile_built(self, knowledge, tmp_path):
        # Write a real profile
        profile_path = tmp_path / "knowledge" / "user-profile.md"
        profile_path.write_text(
            "# User Profile\n\n"
            "## Identity\n"
            "- **Name**: Tony Stark\n"
            "- **Role**: CEO of Stark Industries\n"
            "- **Location**: Malibu, CA\n"
            "- **Background**: Engineer, inventor\n"
        )
        await knowledge._load_all()

        onboarding = OnboardingManager(knowledge)
        assert onboarding.needs_onboarding() is False


class TestOnboardingFlow:
    def test_12_questions_defined(self):
        assert len(ONBOARDING_QUESTIONS) == 12

    def test_all_questions_have_required_fields(self):
        for q in ONBOARDING_QUESTIONS:
            assert "id" in q
            assert "category" in q
            assert "question" in q
            assert "knowledge_key" in q

    def test_categories_covered(self):
        categories = {q["category"] for q in ONBOARDING_QUESTIONS}
        assert "identity" in categories
        assert "work" in categories
        assert "communication" in categories
        assert "preferences" in categories
        assert "goals" in categories

    def test_get_intro_message(self, onboarding):
        intro = onboarding.get_intro_message()
        assert "Jarvis" in intro
        assert "Tony Stark" in intro
        assert "Question 1/" in intro

    def test_initial_state(self, onboarding):
        state = onboarding.get_onboarding_state()
        assert state["active"] is True
        assert state["current_question_idx"] == 0
        assert state["answers"] == {}
        assert state["completed"] is False

    def test_process_first_answer(self, onboarding):
        state = onboarding.get_onboarding_state()
        new_state, next_msg = onboarding.process_answer(state, "Tony Stark")

        assert new_state["current_question_idx"] == 1
        assert "name" in new_state["answers"]
        assert new_state["answers"]["name"]["answer"] == "Tony Stark"
        assert next_msg is not None
        assert "Question 2/" in next_msg

    def test_skip_answer(self, onboarding):
        state = onboarding.get_onboarding_state()
        new_state, _ = onboarding.process_answer(state, "skip")

        assert new_state["current_question_idx"] == 1
        assert "name" not in new_state["answers"]

    def test_full_flow_completes(self, onboarding):
        state = onboarding.get_onboarding_state()

        for i in range(len(ONBOARDING_QUESTIONS)):
            state, next_msg = onboarding.process_answer(state, f"Answer {i}")

        assert state["completed"] is True
        assert state["active"] is False
        assert next_msg is None

    def test_completion_message_uses_name(self, onboarding):
        answers = {
            "name": {"answer": "Bogdan", "category": "identity", "knowledge_key": "Name", "question": "?"}
        }
        msg = onboarding.get_completion_message(answers)
        assert "Bogdan" in msg


class TestProfileBuilding:
    def test_build_profile_from_answers(self, onboarding):
        answers = {
            "name": {
                "answer": "Tony Stark",
                "category": "identity",
                "knowledge_key": "Name",
                "question": "What should I call you?",
            },
            "role": {
                "answer": "CEO / Engineer",
                "category": "identity",
                "knowledge_key": "Role/Profession",
                "question": "What do you do?",
            },
            "language": {
                "answer": "English",
                "category": "communication",
                "knowledge_key": "Preferred Language",
                "question": "What language?",
            },
        }

        profile = onboarding.build_profile_from_answers(answers)
        assert "Tony Stark" in profile
        assert "CEO / Engineer" in profile
        assert "English" in profile
        assert "## Identity" in profile
        assert "## Communication" in profile

    @pytest.mark.asyncio
    async def test_save_profile_writes_to_disk(self, onboarding, knowledge, tmp_path):
        state = {
            "answers": {
                "name": {
                    "answer": "Test User",
                    "category": "identity",
                    "knowledge_key": "Name",
                    "question": "Name?",
                },
            }
        }

        await onboarding.save_profile(state)

        profile_path = tmp_path / "knowledge" / "user-profile.md"
        content = profile_path.read_text()
        assert "Test User" in content
