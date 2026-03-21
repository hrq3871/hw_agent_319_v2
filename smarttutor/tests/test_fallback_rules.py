import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.guardrail_agent import guardrail_agent
from agents.triage_agent import triage_agent
from agents.conversation import conversation_manager
from agents.orchestrator import orchestrator


def test_triage_fallback_handles_short_core_cases():
    assert triage_agent._fallback_classification("x+1=2")["category"] == "valid_math"
    assert triage_agent._fallback_classification("Who was the first president of France?")["category"] == "valid_history"
    assert triage_agent._fallback_classification("I am a first-year university student")["action"] == "handle_grade_info"
    assert triage_agent._fallback_classification("I am a primary school student")["action"] == "handle_grade_info"
    assert triage_agent._fallback_classification("Can you explain calculus?")["category"] == "valid_math"
    assert triage_agent._fallback_classification("Summarize our conversation")["action"] == "handle_summarize"
    assert triage_agent._fallback_classification("hi")["intent"] == "chit_chat"
    assert triage_agent._fallback_classification("thanks")["intent"] == "chit_chat"


def test_explicit_summary_requests_do_not_fall_into_chitchat():
    conversation_summary = triage_agent._fallback_classification("please help me conclude this conversation")
    topic_summary = triage_agent._fallback_classification("conclude this topic")

    assert conversation_summary["action"] == "handle_summarize"
    assert conversation_summary["summary_scope"] == "conversation"
    assert topic_summary["action"] == "handle_summarize"
    assert topic_summary["summary_scope"] == "topic"
    assert orchestrator._looks_like_simple_chit_chat("this") is False
    assert orchestrator._looks_like_simple_chit_chat("conclude this topic") is False


def test_conversation_extract_grade_handles_primary_school():
    assert conversation_manager.extract_grade_from_message("我是小学生") == "primary school student"
    assert conversation_manager.extract_grade_from_message("I am a primary school student") == "primary school student"


def test_chinese_inputs_still_work_with_english_defaults():
    assert triage_agent._fallback_classification("谁是法国第一任总统？")["category"] == "valid_history"
    assert triage_agent._fallback_classification("我是大一学生")["action"] == "handle_grade_info"
    assert triage_agent._fallback_classification("总结我们的对话")["action"] == "handle_summarize"
    assert conversation_manager.extract_grade_from_message("我是大一学生") == "first-year university student"


def test_triage_prefers_obvious_math_fallback_when_llm_is_too_strict(monkeypatch):
    monkeypatch.setattr(
        triage_agent.llm_client,
        "structured_output",
        lambda **kwargs: {
            "category": "invalid",
            "intent": "chit_chat",
            "reason": "too broad",
            "action": "respond_rejection",
        },
    )

    result = triage_agent.classify_sync("Can you explain calculus?")

    assert result["category"] == "valid_math"
    assert result["action"] == "handoff_to_math"


def test_content_summary_request_is_not_forced_into_conversation_summary(monkeypatch):
    monkeypatch.setattr(
        triage_agent.llm_client,
        "structured_output",
        lambda **kwargs: {
            "category": "valid_history",
            "intent": "ask_question",
            "reason": "history_content_summary",
            "action": "handoff_to_history",
        },
    )

    result = triage_agent.classify_sync("Give me a summary of the French Revolution")

    assert result["category"] == "valid_history"
    assert result["action"] == "handoff_to_history"


def test_simple_chitchat_fast_path_skips_triage_llm(monkeypatch):
    class ShouldNotCallLLM(BaseException):
        pass

    def fail_structured_output(**kwargs):
        raise ShouldNotCallLLM("triage LLM should not run for simple chitchat fast path")

    monkeypatch.setattr(triage_agent.llm_client, "structured_output", fail_structured_output)

    result = triage_agent.classify_sync("hi")

    assert result["intent"] == "chit_chat"
    assert result["action"] == "respond_chitchat"


def test_obvious_math_fast_path_skips_triage_llm(monkeypatch):
    class ShouldNotCallLLM(BaseException):
        pass

    def fail_structured_output(**kwargs):
        raise ShouldNotCallLLM("triage LLM should not run for obvious math fast path")

    monkeypatch.setattr(triage_agent.llm_client, "structured_output", fail_structured_output)

    result = triage_agent.classify_sync("x+1=2")

    assert result["category"] == "valid_math"
    assert result["action"] == "handoff_to_math"


def test_guardrail_rule_based_check_rejects_travel_question():
    should_reject, message = guardrail_agent._rule_based_check("去伦敦怎么走？")

    assert should_reject is True
    assert "not a math or history homework question" in message


def test_guardrail_rule_based_check_rejects_too_local_question():
    should_reject, message = guardrail_agent._rule_based_check("HKUST第一任校长是谁？")

    assert should_reject is True
    assert "too local" in message or "niche" in message
