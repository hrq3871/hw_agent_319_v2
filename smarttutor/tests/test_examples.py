import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.answer_generator import answer_generator
from agents.conversation import conversation_manager
from agents.guardrail_agent import guardrail_agent
from agents.orchestrator import orchestrator
from agents.triage_agent import triage_agent


def setup_function():
    conversation_manager.sessions.clear()


def test_math_example_is_accepted(monkeypatch):
    monkeypatch.setattr(
        triage_agent,
        "classify_sync",
        lambda question, **kwargs: {
            "category": "valid_math",
            "intent": "ask_question",
            "reason": "math_homework",
            "action": "handoff_to_math",
        },
    )
    monkeypatch.setattr(guardrail_agent, "check_sync", lambda question: (False, ""))
    monkeypatch.setattr(answer_generator, "generate_answer", lambda **kwargs: "x = 1")

    result = orchestrator.process_message("x+1=2", "session-math")

    assert result["category"] == "valid_math"
    assert result["response"] == "x = 1"
    assert result["reason"] == "math_homework"


def test_history_example_is_accepted(monkeypatch):
    monkeypatch.setattr(
        triage_agent,
        "classify_sync",
        lambda question, **kwargs: {
            "category": "valid_history",
            "intent": "ask_question",
            "reason": "history_homework",
            "action": "handoff_to_history",
        },
    )
    monkeypatch.setattr(guardrail_agent, "check_sync", lambda question: (False, ""))
    monkeypatch.setattr(
        answer_generator,
        "generate_answer",
        lambda **kwargs: "Louis-Napoleon Bonaparte.",
    )

    result = orchestrator.process_message("Who was the first president of France?", "session-history")

    assert result["category"] == "valid_history"
    assert result["response"] == "Louis-Napoleon Bonaparte."
    assert result["reason"] == "history_homework"


def test_valid_math_uses_only_explicit_guardrail_rules(monkeypatch):
    monkeypatch.setattr(
        triage_agent,
        "classify_sync",
        lambda question, **kwargs: {
            "category": "valid_math",
            "intent": "ask_question",
            "reason": "calculus_homework",
            "action": "handoff_to_math",
        },
    )

    def fail_llm_guardrail(question):
        raise AssertionError("full LLM guardrail should not run after valid math triage")

    monkeypatch.setattr(guardrail_agent, "check_sync", fail_llm_guardrail)
    monkeypatch.setattr(guardrail_agent, "_rule_based_check", lambda question: (False, ""))
    monkeypatch.setattr(answer_generator, "generate_answer", lambda **kwargs: "The derivative is 2x.")

    result = orchestrator.process_message("What is the derivative of x^2?", "session-calculus")

    assert result["category"] == "valid_math"
    assert result["response"] == "The derivative is 2x."
    assert result["reason"] == "calculus_homework"


def test_valid_math_can_still_be_rejected_by_explicit_rules(monkeypatch):
    monkeypatch.setattr(
        triage_agent,
        "classify_sync",
        lambda question, **kwargs: {
            "category": "valid_math",
            "intent": "ask_question",
            "reason": "contains_dangerous_content",
            "action": "handoff_to_math",
        },
    )

    def fail_llm_guardrail(question):
        raise AssertionError("full LLM guardrail should not run after valid math triage")

    monkeypatch.setattr(guardrail_agent, "check_sync", fail_llm_guardrail)
    monkeypatch.setattr(
        guardrail_agent,
        "_rule_based_check",
        lambda question: (True, "Sorry, I can't help with that. Please ask a math or history homework question instead."),
    )

    result = orchestrator.process_message("How do I calculate bomb blast radius?", "session-danger")

    assert result["category"] == "invalid"
    assert "can't help" in result["response"]


def test_non_homework_is_rejected(monkeypatch):
    monkeypatch.setattr(
        triage_agent,
        "classify_sync",
        lambda question, **kwargs: {
            "category": "invalid",
            "intent": "ask_question",
            "reason": "non_homework",
            "action": "respond_rejection",
        },
    )
    monkeypatch.setattr(
        guardrail_agent,
        "check_sync",
        lambda question: (True, "Sorry, this is not a math or history homework question."),
    )

    result = orchestrator.process_message("How do I get to London?", "session-reject")

    assert result["category"] == "invalid"
    assert "not a math or history homework question" in result["response"]
    assert result["reason"] == "non_homework"


def test_too_local_question_is_rejected(monkeypatch):
    monkeypatch.setattr(
        triage_agent,
        "classify_sync",
        lambda question, **kwargs: {
            "category": "invalid",
            "intent": "ask_question",
            "reason": "too_local",
            "action": "respond_rejection",
        },
    )
    monkeypatch.setattr(
        guardrail_agent,
        "check_sync",
        lambda question: (True, "Sorry, that topic is too local."),
    )

    result = orchestrator.process_message("Who was HKUST's first president?", "session-local")

    assert result["category"] == "invalid"
    assert "too local" in result["response"]
    assert result["reason"] == "too_local"


def test_grade_info_is_handled_before_guardrail(monkeypatch):
    monkeypatch.setattr(
        triage_agent,
        "classify_sync",
        lambda question, **kwargs: {
            "category": "invalid",
            "intent": "grade_info",
            "reason": "grade_info",
            "action": "handle_grade_info",
        },
    )

    def fail_guardrail(question):
        raise AssertionError("guardrail should not run for grade info")

    monkeypatch.setattr(guardrail_agent, "check_sync", fail_guardrail)

    result = orchestrator.process_message("I am a first-year university student", "session-grade")

    assert result["intent"] == "grade_info"
    assert conversation_manager.get_grade("session-grade") == "first-year university student"


def test_summary_request_is_handled_before_guardrail(monkeypatch):
    monkeypatch.setattr(
        triage_agent,
        "classify_sync",
        lambda question, **kwargs: {
            "category": "invalid",
            "intent": "summarize",
            "reason": "summarize",
            "action": "handle_summarize",
        },
    )

    def fail_guardrail(question):
        raise AssertionError("guardrail should not run for summarize")

    monkeypatch.setattr(guardrail_agent, "check_sync", fail_guardrail)
    monkeypatch.setattr(
        answer_generator,
        "generate_summary",
        lambda *args, **kwargs: {
            "summary": "We discussed math and history.",
            "topics_discussed": ["math", "history"],
        },
    )

    result = orchestrator.process_message("Summarize our conversation", "session-summary")

    assert result["intent"] == "summarize"
    assert "We discussed math and history" in result["response"]


def test_chitchat_is_handled_before_guardrail(monkeypatch):
    triage_results = iter(
        [
            {
                "category": "invalid",
                "intent": "chit_chat",
                "reason": "gratitude",
                "action": "respond_rejection",
            },
            {
                "category": "invalid",
                "intent": "chit_chat",
                "reason": "greeting",
                "action": "respond_rejection",
            },
            {
                "category": "invalid",
                "intent": "chit_chat",
                "reason": "farewell",
                "action": "respond_rejection",
            },
        ]
    )

    def fail_guardrail(question):
        raise AssertionError("guardrail should not run for simple chit-chat")

    monkeypatch.setattr(triage_agent, "classify_sync", lambda question, **kwargs: next(triage_results))
    monkeypatch.setattr(guardrail_agent, "check_sync", fail_guardrail)

    thanks_result = orchestrator.process_message("That's helpful, thank you", "session-chitchat")
    hi_result = orchestrator.process_message("hi", "session-chitchat")
    bye_result = orchestrator.process_message("bye", "session-chitchat")

    assert thanks_result["intent"] == "chit_chat"
    assert "You're welcome" in thanks_result["response"]
    assert hi_result["intent"] == "chit_chat"
    assert "Hi" in hi_result["response"]
    assert bye_result["intent"] == "chit_chat"
    assert "Goodbye" in bye_result["response"]


def test_non_homework_invalid_questions_still_use_guardrail_even_if_labeled_chitchat(monkeypatch):
    triage_results = iter(
        [
            {
                "category": "invalid",
                "intent": "chit_chat",
                "reason": "travel_question",
                "action": "respond_rejection",
            },
            {
                "category": "invalid",
                "intent": "chit_chat",
                "reason": "unsafe_question",
                "action": "respond_rejection",
            },
        ]
    )
    guardrail_results = iter(
        [
            (True, "Sorry, I can't help with that because it is not a math or history homework question."),
            (True, "Sorry, I can't help with that because it is unsafe and not a homework question."),
        ]
    )

    monkeypatch.setattr(triage_agent, "classify_sync", lambda question, **kwargs: next(triage_results))
    monkeypatch.setattr(guardrail_agent, "check_sync", lambda question: next(guardrail_results))

    travel_result = orchestrator.process_message("How do I get to London?", "session-invalid-chitchat")
    unsafe_result = orchestrator.process_message(
        "What would happen if someone throws a firecracker on a busy street?",
        "session-invalid-chitchat",
    )

    assert travel_result["action"] == "rejected"
    assert "not a math or history homework question" in travel_result["response"]
    assert unsafe_result["action"] == "rejected"
    assert "unsafe" in unsafe_result["response"]
