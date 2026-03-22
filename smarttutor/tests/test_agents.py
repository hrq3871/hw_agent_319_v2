import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from agents.answer_generator import answer_generator
from agents.conversation import ConversationManager
from agents.multi_model_client import MultiModelClient


def test_conversation_manager_add_message_creates_missing_session():
    manager = ConversationManager()

    manager.add_message("session-1", "user", "hi")

    assert manager.get_history("session-1") == [{"role": "user", "content": "hi"}]


def test_conversation_manager_set_grade_creates_missing_session():
    manager = ConversationManager()

    manager.set_grade("session-2", "first-year university student")

    assert manager.get_grade("session-2") == "first-year university student"


def test_llm_client_module_imports_cleanly():
    module = importlib.import_module("agents.llm_client")

    assert hasattr(module, "llm_client")


def test_multi_model_client_falls_back_when_math_model_is_denied():
    class DeniedLLM:
        def invoke(self, messages):
            raise RuntimeError("team_model_access_denied: o1-mini")

    class WorkingLLM:
        def __init__(self):
            self.calls = 0

        def invoke(self, messages):
            self.calls += 1
            return type("Response", (), {"content": "fallback answer"})()

    client = MultiModelClient()
    client._initialized = True
    default_llm = WorkingLLM()
    client._llms = {
        "math": DeniedLLM(),
        "default": default_llm,
    }

    result = client.chat("x+1=2", task="math")

    assert result == "fallback answer"
    assert default_llm.calls == 1


def test_answer_generator_retries_when_model_refuses_only_due_to_grade(monkeypatch):
    calls = []

    def fake_chat(message, system_prompt, task="default"):
        calls.append({"message": message, "system_prompt": system_prompt, "task": task})
        if len(calls) == 1:
            return "Sorry, I can't help with that because derivatives may be too advanced for a primary school student."
        return "This is advanced, but you can start with this: the derivative of x^2 is 2x."

    monkeypatch.setattr(answer_generator.llm_client, "chat", fake_chat)
    monkeypatch.setattr(answer_generator.conversation_manager, "get_history", lambda session_id: [])

    result = answer_generator.generate_answer(
        question="What is the derivative of x^2?",
        session_id="session-retry-grade",
        category="valid_math",
        grade="primary school student",
    )

    assert "2x" in result
    assert len(calls) == 2
