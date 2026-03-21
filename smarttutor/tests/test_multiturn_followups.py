import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.answer_generator import answer_generator
from agents.conversation import conversation_manager
from agents.guardrail_agent import guardrail_agent
from agents.orchestrator import orchestrator
from agents.triage_agent import triage_agent


def setup_function():
    conversation_manager.sessions.clear()


def test_math_followup_should_continue_answering(monkeypatch):
    triage_results = iter(
        [
            {
                "category": "valid_math",
                "intent": "ask_question",
                "reason": "math_homework",
                "action": "handoff_to_math",
            },
            {
                "category": "valid_math",
                "intent": "ask_question",
                "reason": "follow_up_from_context",
                "action": "handoff_to_math",
            },
        ]
    )
    answers = iter(
        [
            "x = 1",
            "Because subtracting 1 from both sides keeps the equation balanced.",
        ]
    )

    monkeypatch.setattr(triage_agent, "classify_sync", lambda *args, **kwargs: next(triage_results))
    monkeypatch.setattr(guardrail_agent, "check_sync", lambda _: (False, ""))
    monkeypatch.setattr(answer_generator, "generate_answer", lambda **_: next(answers))

    session_id = "math-followup"
    first = orchestrator.process_message("x+1=2", session_id)
    second = orchestrator.process_message("Why subtract 1 on both sides?", session_id)

    assert first["category"] == "valid_math"
    assert second["category"] == "valid_math"
    assert "balanced" in second["response"]


def test_history_followup_should_continue_answering(monkeypatch):
    triage_results = iter(
        [
            {
                "category": "valid_history",
                "intent": "ask_question",
                "reason": "history_homework",
                "action": "handoff_to_history",
            },
            {
                "category": "valid_history",
                "intent": "ask_question",
                "reason": "history_follow_up",
                "action": "handoff_to_history",
            },
        ]
    )
    answers = iter(
        [
            "Louis-Napoleon Bonaparte was the first president of France.",
            "He took office in 1848.",
        ]
    )

    monkeypatch.setattr(triage_agent, "classify_sync", lambda *args, **kwargs: next(triage_results))
    monkeypatch.setattr(guardrail_agent, "check_sync", lambda _: (False, ""))
    monkeypatch.setattr(answer_generator, "generate_answer", lambda **_: next(answers))

    session_id = "history-followup"
    orchestrator.process_message("Who was the first president of France?", session_id)
    second = orchestrator.process_message("What year did he take office?", session_id)

    assert second["category"] == "valid_history"
    assert "1848" in second["response"]


def test_clarification_can_switch_from_reject_to_accept(monkeypatch):
    triage_results = iter(
        [
            {
                "category": "invalid",
                "intent": "ask_question",
                "reason": "travel_question",
                "action": "respond_rejection",
            },
            {
                "category": "valid_math",
                "intent": "ask_question",
                "reason": "distance_math_question",
                "action": "handoff_to_math",
            },
        ]
    )
    guardrail_results = iter(
        [
            (True, "Sorry, this is not a math or history homework question."),
            (False, ""),
        ]
    )

    monkeypatch.setattr(triage_agent, "classify_sync", lambda *args, **kwargs: next(triage_results))
    monkeypatch.setattr(guardrail_agent, "check_sync", lambda _: next(guardrail_results))
    monkeypatch.setattr(
        answer_generator,
        "generate_answer",
        lambda **_: "You can compute it with a great-circle distance formula.",
    )

    session_id = "clarification-switch"
    first = orchestrator.process_message("How do I get to London?", session_id)
    second = orchestrator.process_message(
        "I mean how to calculate the straight-line distance from Hong Kong to London.",
        session_id,
    )

    assert first["category"] == "invalid"
    assert second["category"] == "valid_math"
    assert "distance" in second["response"]


def test_summary_followup_should_not_be_rejected(monkeypatch):
    triage_results = iter(
        [
            {
                "category": "invalid",
                "intent": "summarize",
                "reason": "summarize_request",
                "action": "handle_summarize",
            },
            {
                "category": "invalid",
                "intent": "summarize",
                "reason": "summary_refinement",
                "action": "handle_summarize",
            },
        ]
    )
    summaries = iter(
        [
            {"summary": "We discussed math and history.", "topics_discussed": ["math", "history"]},
            {"summary": "Math and history were discussed.", "topics_discussed": ["math", "history"]},
        ]
    )

    monkeypatch.setattr(triage_agent, "classify_sync", lambda *args, **kwargs: next(triage_results))

    def fail_guardrail(_):
        raise AssertionError("guardrail should not run for summary follow-ups")

    monkeypatch.setattr(guardrail_agent, "check_sync", fail_guardrail)
    monkeypatch.setattr(answer_generator, "generate_summary", lambda *args, **kwargs: next(summaries))

    session_id = "summary-followup"
    first = orchestrator.process_message("Summarize our conversation", session_id)
    second = orchestrator.process_message("Make it shorter.", session_id)

    assert first["intent"] == "summarize"
    assert second["intent"] == "summarize"
    assert "Math and history" in second["response"]


def test_primary_school_student_can_ask_advanced_math_without_rejection(monkeypatch):
    triage_results = iter(
        [
            {
                "category": "invalid",
                "intent": "grade_info",
                "reason": "grade_info",
                "action": "handle_grade_info",
            },
            {
                "category": "valid_math",
                "intent": "ask_question",
                "reason": "advanced_math_question",
                "action": "handoff_to_math",
            },
        ]
    )
    captured = {}

    monkeypatch.setattr(triage_agent, "classify_sync", lambda *args, **kwargs: next(triage_results))
    monkeypatch.setattr(guardrail_agent, "check_sync", lambda _: (False, ""))

    def fake_generate_answer(**kwargs):
        captured["grade"] = kwargs["grade"]
        return "This topic is advanced for primary school, but here is a simple explanation."

    monkeypatch.setattr(answer_generator, "generate_answer", fake_generate_answer)

    session_id = "primary-advanced-math"
    first = orchestrator.process_message("I am a primary school student", session_id)
    second = orchestrator.process_message("Can you explain calculus?", session_id)

    assert first["intent"] == "grade_info"
    assert conversation_manager.get_grade(session_id) == "primary school student"
    assert second["category"] == "valid_math"
    assert captured["grade"] == "primary school student"
    assert "simple explanation" in second["response"]


def test_short_followup_uses_previous_history_context(monkeypatch):
    responses = {
        "Who was the first president of France?": {
            "category": "valid_history",
            "intent": "ask_question",
            "reason": "history_homework",
            "action": "handoff_to_history",
        },
        "and more?": {
            "category": "invalid",
            "intent": "chit_chat",
            "reason": "too vague",
            "action": "respond_rejection",
        },
    }
    answers = iter(
        [
            "Louis-Napoleon Bonaparte was the first president of France.",
            "He was elected in 1848 and later became Emperor Napoleon III in 1852.",
        ]
    )

    monkeypatch.setattr(triage_agent, "classify_sync", lambda message, **kwargs: responses[message])
    monkeypatch.setattr(
        guardrail_agent,
        "check_sync",
        lambda message: (True, "This should not be used for contextual follow-ups."),
    )
    monkeypatch.setattr(guardrail_agent, "_rule_based_check", lambda message: (False, ""))
    monkeypatch.setattr(answer_generator, "generate_answer", lambda **kwargs: next(answers))

    session_id = "history-short-followup"
    first = orchestrator.process_message("Who was the first president of France?", session_id)
    second = orchestrator.process_message("and more?", session_id)

    assert first["category"] == "valid_history"
    assert second["category"] == "valid_history"
    assert "Napoleon III" in second["response"]


def test_natural_followup_uses_active_learning_context(monkeypatch):
    answers = iter(
        [
            "Louis-Napoleon Bonaparte was the first president of France.",
            "He later became Emperor Napoleon III in 1852.",
            "Because he ended the republic and created the Second French Empire.",
        ]
    )

    def classify(message, context=None):
        if message == "Who was the first president of France?":
            return {
                "category": "valid_history",
                "intent": "ask_question",
                "reason": "history_homework",
                "action": "handoff_to_history",
            }

        assert context is not None
        assert context["active_learning_context"]["category"] == "valid_history"
        return {
            "category": "invalid",
            "intent": "follow_up",
            "reason": "contextual_follow_up",
            "action": "handle_follow_up",
        }

    monkeypatch.setattr(triage_agent, "classify_sync", classify)
    monkeypatch.setattr(guardrail_agent, "check_sync", lambda _: (False, ""))
    monkeypatch.setattr(guardrail_agent, "_rule_based_check", lambda _: (False, ""))
    monkeypatch.setattr(answer_generator, "generate_answer", lambda **kwargs: next(answers))

    session_id = "natural-followup-active-context"
    first = orchestrator.process_message("Who was the first president of France?", session_id)
    second = orchestrator.process_message("say something more", session_id)
    third = orchestrator.process_message("why", session_id)

    assert first["category"] == "valid_history"
    assert second["intent"] == "follow_up"
    assert second["category"] == "valid_history"
    assert "Napoleon III" in second["response"]
    assert third["category"] == "valid_history"
    assert "Second French Empire" in third["response"]


def test_why_after_real_rejection_explains_rejection(monkeypatch):
    def classify(message, context=None):
        if message == "How do I get to London?":
            return {
                "category": "invalid",
                "intent": "ask_question",
                "reason": "travel_question",
                "action": "respond_rejection",
            }

        assert context is not None
        assert context["last_rejection_info"]["reason"] == "travel_question"
        return {
            "category": "invalid",
            "intent": "follow_up",
            "reason": "rejection_follow_up",
            "action": "handle_follow_up",
        }

    monkeypatch.setattr(triage_agent, "classify_sync", classify)
    monkeypatch.setattr(
        guardrail_agent,
        "check_sync",
        lambda _: (True, "Sorry, this is not a math or history homework question."),
    )

    session_id = "why-after-rejection"
    first = orchestrator.process_message("How do I get to London?", session_id)
    second = orchestrator.process_message("why", session_id)

    assert first["category"] == "invalid"
    assert second["intent"] == "follow_up"
    assert second["action"] == "explained_rejection"
    assert "not a math or history homework question" in second["response"]


def test_contextual_practice_request_uses_recent_valid_topic(monkeypatch):
    def classify(message, context=None):
        if message == "x+1=2":
            return {
                "category": "valid_math",
                "intent": "ask_question",
                "reason": "math_homework",
                "action": "handoff_to_math",
            }

        assert context is not None
        assert context["active_learning_context"]["category"] == "valid_math"
        return {
            "category": "invalid",
            "intent": "practice_request",
            "reason": "contextual_practice_request",
            "action": "handle_practice_request",
        }

    captured = {}
    monkeypatch.setattr(triage_agent, "classify_sync", classify)
    monkeypatch.setattr(guardrail_agent, "check_sync", lambda _: (False, ""))
    monkeypatch.setattr(guardrail_agent, "_rule_based_check", lambda _: (False, ""))
    monkeypatch.setattr(answer_generator, "generate_answer", lambda **kwargs: "x = 1")

    def fake_generate_practice(**kwargs):
        captured.update(kwargs)
        return "1. Solve x+2=5\nHint: subtract 2.\n\n2. Solve x+4=9\nHint: isolate x.\n\n3. Solve x-3=7\nHint: undo subtraction."

    monkeypatch.setattr(answer_generator, "generate_practice", fake_generate_practice)

    session_id = "context-practice-request"
    orchestrator.process_message("x+1=2", session_id)
    result = orchestrator.process_message("give me 3 practice questions about this", session_id)

    assert result["intent"] == "practice_request"
    assert result["action"] == "practice_generated"
    assert captured["category"] == "valid_math"
    assert captured["count"] == 3
    assert "x+1=2" in captured["topic_seed"]


def test_explicit_topic_practice_request_without_context_is_answered(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        triage_agent,
        "classify_sync",
        lambda message, **kwargs: {
            "category": "valid_math",
            "intent": "practice_request",
            "reason": "explicit_math_practice_request",
            "action": "handle_practice_request",
        },
    )

    def fake_generate_practice(**kwargs):
        captured.update(kwargs)
        return "1. Simplify 2x + 3x\nHint: combine like terms."

    monkeypatch.setattr(answer_generator, "generate_practice", fake_generate_practice)

    result = orchestrator.process_message("Give me algebra exercises", "explicit-practice")

    assert result["intent"] == "practice_request"
    assert result["action"] == "practice_generated"
    assert captured["category"] == "valid_math"
    assert "algebra" in captured["topic_seed"].lower()


def test_practice_request_without_topic_clarifies_instead_of_rejecting(monkeypatch):
    monkeypatch.setattr(
        triage_agent,
        "classify_sync",
        lambda message, **kwargs: {
            "category": "invalid",
            "intent": "practice_request",
            "reason": "missing_topic_for_practice",
            "action": "handle_practice_request",
        },
    )

    result = orchestrator.process_message("Give me some exercises", "practice-clarify")

    assert result["intent"] == "practice_request"
    assert result["action"] == "clarification_requested"
    assert "math or history topic" in result["response"]


def test_rejected_topic_does_not_become_practice_source(monkeypatch):
    responses = {
        "Who is HKUST's first president?": {
            "category": "invalid",
            "intent": "ask_question",
            "reason": "too_local",
            "action": "respond_rejection",
        },
        "give me some exercises": {
            "category": "invalid",
            "intent": "practice_request",
            "reason": "missing_topic_for_practice",
            "action": "handle_practice_request",
        },
    }

    def classify(message, context=None):
        if message == "give me some exercises":
            assert context is not None
            assert context["active_learning_context"] is None
            assert context["last_rejection_info"]["reason"] == "too_local"
        return responses[message]

    monkeypatch.setattr(triage_agent, "classify_sync", classify)
    monkeypatch.setattr(guardrail_agent, "check_sync", lambda _: (True, "Sorry, that topic is too local."))

    result = orchestrator.process_message("Who is HKUST's first president?", "rejected-practice-source")
    assert result["category"] == "invalid"

    second = orchestrator.process_message("give me some exercises", "rejected-practice-source")
    assert second["intent"] == "practice_request"
    assert second["action"] == "clarification_requested"
    assert "math or history topic" in second["response"]


def test_topic_summary_uses_only_latest_accepted_subject_thread(monkeypatch):
    responses = {
        "x+1=-2": {
            "category": "valid_math",
            "intent": "ask_question",
            "reason": "math_homework",
            "action": "handoff_to_math",
        },
        "Who is HKUST's first president?": {
            "category": "invalid",
            "intent": "ask_question",
            "reason": "too_local",
            "action": "respond_rejection",
        },
        "Who was the first president of France?": {
            "category": "valid_history",
            "intent": "ask_question",
            "reason": "history_homework",
            "action": "handoff_to_history",
        },
        "conclude this topic": {
            "category": "invalid",
            "intent": "summarize",
            "reason": "topic_summary",
            "action": "handle_summarize",
            "summary_scope": "topic",
        },
    }
    answers = {
        "x+1=-2": "x = -3",
        "Who was the first president of France?": "Louis-Napoleon Bonaparte was the first president of France.",
    }
    captured = {}

    monkeypatch.setattr(triage_agent, "classify_sync", lambda message, **kwargs: responses[message])
    monkeypatch.setattr(
        guardrail_agent,
        "_rule_based_check",
        lambda message: (False, "") if message != "Who is HKUST's first president?" else (True, "Sorry, that topic is too local."),
    )
    monkeypatch.setattr(
        guardrail_agent,
        "check_sync",
        lambda message: (True, "Sorry, that topic is too local.") if message == "Who is HKUST's first president?" else (False, ""),
    )
    monkeypatch.setattr(answer_generator, "generate_answer", lambda question, **kwargs: answers[question])

    def fake_structured_output(**kwargs):
        captured["system_prompt"] = kwargs["system_prompt"]
        return {
            "summary": "We focused on the France history topic.",
            "topics_discussed": ["history"],
            "unanswered_questions": [],
        }

    monkeypatch.setattr(answer_generator.llm_client, "structured_output", fake_structured_output)

    session_id = "topic-summary-scope"
    orchestrator.process_message("x+1=-2", session_id)
    orchestrator.process_message("Who is HKUST's first president?", session_id)
    orchestrator.process_message("Who was the first president of France?", session_id)
    result = orchestrator.process_message("conclude this topic", session_id)

    assert result["intent"] == "summarize"
    assert "France history topic" in result["response"]
    assert "Who was the first president of France?" in captured["system_prompt"]
    assert "Louis-Napoleon Bonaparte" in captured["system_prompt"]
    assert "Who is HKUST's first president?" not in captured["system_prompt"]
    assert "x+1=-2" not in captured["system_prompt"]


def test_conversation_summary_keeps_brief_reliability_evidence(monkeypatch):
    responses = {
        "x+1=-2": {
            "category": "valid_math",
            "intent": "ask_question",
            "reason": "math_homework",
            "action": "handoff_to_math",
        },
        "Who is HKUST's first president?": {
            "category": "invalid",
            "intent": "ask_question",
            "reason": "too_local",
            "action": "respond_rejection",
        },
        "Who was the first president of France?": {
            "category": "valid_history",
            "intent": "ask_question",
            "reason": "history_homework",
            "action": "handoff_to_history",
        },
        "please help me conclude this conversation": {
            "category": "invalid",
            "intent": "summarize",
            "reason": "conversation_summary",
            "action": "handle_summarize",
            "summary_scope": "conversation",
        },
    }
    answers = {
        "x+1=-2": "x = -3",
        "Who was the first president of France?": "Louis-Napoleon Bonaparte was the first president of France.",
    }
    captured = {}

    monkeypatch.setattr(triage_agent, "classify_sync", lambda message, **kwargs: responses[message])
    monkeypatch.setattr(
        guardrail_agent,
        "_rule_based_check",
        lambda message: (False, "") if message != "Who is HKUST's first president?" else (True, "Sorry, that topic is too local."),
    )
    monkeypatch.setattr(
        guardrail_agent,
        "check_sync",
        lambda message: (True, "Sorry, that topic is too local.") if message == "Who is HKUST's first president?" else (False, ""),
    )
    monkeypatch.setattr(answer_generator, "generate_answer", lambda question, **kwargs: answers[question])

    def fake_structured_output(**kwargs):
        captured["system_prompt"] = kwargs["system_prompt"]
        return {
            "summary": "We discussed math and history, and one HKUST request was rejected as too local.",
            "topics_discussed": ["math", "history"],
            "unanswered_questions": [],
        }

    monkeypatch.setattr(answer_generator.llm_client, "structured_output", fake_structured_output)

    session_id = "conversation-summary-evidence"
    orchestrator.process_message("x+1=-2", session_id)
    orchestrator.process_message("Who is HKUST's first president?", session_id)
    orchestrator.process_message("Who was the first president of France?", session_id)
    result = orchestrator.process_message("please help me conclude this conversation", session_id)

    assert result["intent"] == "summarize"
    assert "too local" in result["response"]
    assert "Assistant [rejected" in captured["system_prompt"]
    assert "Who is HKUST's first president?" in captured["system_prompt"]
    assert "x+1=-2" in captured["system_prompt"]
    assert "Who was the first president of France?" in captured["system_prompt"]


@pytest.mark.parametrize(
    ("question", "triage_result", "guardrail_result", "expected_category"),
    [
        (
            "How do you compute the straight-line distance between two cities?",
            {
                "category": "valid_math",
                "intent": "ask_question",
                "reason": "distance_math_question",
                "action": "handoff_to_math",
            },
            (False, ""),
            "valid_math",
        ),
        (
            "What is the best route to London?",
            {
                "category": "invalid",
                "intent": "ask_question",
                "reason": "travel_question",
                "action": "respond_rejection",
            },
            (True, "Sorry, this is not a math or history homework question."),
            "invalid",
        ),
        (
            "Write Python code to solve x+1=2",
            {
                "category": "invalid",
                "intent": "ask_question",
                "reason": "programming_request",
                "action": "respond_rejection",
            },
            (True, "Sorry, this is outside math and history homework scope."),
            "invalid",
        ),
        (
            "Should I buy Bitcoin? Please use expected value.",
            {
                "category": "invalid",
                "intent": "ask_question",
                "reason": "financial_advice",
                "action": "respond_rejection",
            },
            (True, "Sorry, this is not a math or history homework question."),
            "invalid",
        ),
        (
            "Is square root of 1000 rational?",
            {
                "category": "valid_math",
                "intent": "ask_question",
                "reason": "math_homework",
                "action": "handoff_to_math",
            },
            (False, ""),
            "valid_math",
        ),
        (
            "Who was HKUST's first president?",
            {
                "category": "invalid",
                "intent": "ask_question",
                "reason": "too_local",
                "action": "respond_rejection",
            },
            (True, "Sorry, this is too local to count as a general history homework question."),
            "invalid",
        ),
    ],
)
def test_boundary_cases(monkeypatch, question, triage_result, guardrail_result, expected_category):
    monkeypatch.setattr(triage_agent, "classify_sync", lambda *args, **kwargs: triage_result)
    monkeypatch.setattr(guardrail_agent, "check_sync", lambda _: guardrail_result)

    if expected_category != "invalid":
        monkeypatch.setattr(answer_generator, "generate_answer", lambda **_: "accepted answer")

    result = orchestrator.process_message(question, f"boundary-{expected_category}")

    assert result["category"] == expected_category
    if expected_category == "invalid":
        assert result["response"]
    else:
        assert result["response"] == "accepted answer"
