"""Answer generation utilities for SmartTutor."""

from typing import Any, Dict, List, Tuple

from agents.conversation import conversation_manager
from agents.multi_model_client import multi_model_client
from app.prompts import (
    HISTORY_EXPERT_PROMPT,
    MATH_EXPERT_PROMPT,
    PRACTICE_PROMPT,
    SUMMARY_PROMPT,
    SYSTEM_PROMPT,
)


class AnswerGenerator:
    """Generate tutoring answers, summaries, and practice questions."""

    def __init__(self):
        self.llm_client = multi_model_client
        self.conversation_manager = conversation_manager

    def generate_answer(
        self,
        question: str,
        session_id: str,
        category: str,
        grade: str = None,
    ) -> str:
        """Generate an answer for a math or history tutoring question."""
        history = self.conversation_manager.get_history(session_id)
        grade_info = grade if grade else "unspecified"

        if category == "valid_math":
            system_prompt = self._build_math_prompt(grade_info)
            task = "math"
        elif category == "valid_history":
            system_prompt = self._build_history_prompt(grade_info)
            task = "history"
        else:
            system_prompt = SYSTEM_PROMPT
            task = "default"

        if history:
            context = self._build_context(history)
            full_question = f"{context}\n\nCurrent question: {question}"
        else:
            full_question = question

        response = self.llm_client.chat(full_question, system_prompt, task=task)

        if category in {"valid_math", "valid_history"} and self._needs_simplified_retry(response):
            retry_prompt = self._build_retry_prompt(system_prompt)
            response = self.llm_client.chat(full_question, retry_prompt, task=task)

        return response

    def generate_practice(
        self,
        category: str,
        topic_seed: str,
        grade: str = None,
        count: int = 3,
    ) -> str:
        """Generate topic-aligned practice questions."""
        safe_count = min(max(int(count or 3), 1), 10)
        grade_info = grade if grade else "unspecified"
        subject = "math" if category == "valid_math" else "history"
        task = "math" if category == "valid_math" else "history"
        system_prompt = PRACTICE_PROMPT.format(
            subject=subject,
            grade=grade_info,
            topic_seed=topic_seed,
            count=safe_count,
        )
        return self.llm_client.chat(
            f"Create {safe_count} practice questions based on this topic seed:\n{topic_seed}",
            system_prompt,
            task=task,
        )

    def generate_summary(self, session_id: str, scope: str = "conversation") -> Dict[str, Any]:
        """Generate a conversation or latest-topic summary."""
        history, resolved_scope = self._get_summary_history(session_id, scope)

        if not history:
            return {
                "summary": "The conversation is currently empty.",
                "topics_discussed": [],
                "unanswered_questions": [],
            }

        conversation_history = self._format_summary_history(history)
        prompt = SUMMARY_PROMPT.format(
            summary_target=self._summary_target_label(resolved_scope),
            scope_instructions=self._build_summary_scope_instructions(resolved_scope),
            conversation_history=conversation_history,
        )

        result = self.llm_client.structured_output(
            message="Please summarize the conversation above.",
            system_prompt=prompt,
            task="default",
            format_json=True,
        )

        if "error" in result:
            return self._build_summary_fallback(history, resolved_scope)

        return {
            "summary": result.get("summary", "Unable to generate a summary."),
            "topics_discussed": result.get("topics_discussed", []),
            "unanswered_questions": result.get("unanswered_questions", []),
        }

    def _build_math_prompt(self, grade: str) -> str:
        prompt = MATH_EXPERT_PROMPT.format(grade=grade)
        return f"{prompt}\n\n{SYSTEM_PROMPT}"

    def _build_history_prompt(self, grade: str) -> str:
        prompt = HISTORY_EXPERT_PROMPT.format(grade=grade)
        return f"{prompt}\n\n{SYSTEM_PROMPT}"

    def _build_retry_prompt(self, system_prompt: str) -> str:
        return (
            f"{system_prompt}\n\n"
            "Important: do not refuse only because the user is young or the topic is advanced. "
            "If the question is still about math or history, first say that it is advanced, then explain the core idea more simply, "
            "and try to provide at least the basic answer, conclusion, or first step. "
            "Only refuse if the question is not about math/history or is inappropriate."
        )

    def _needs_simplified_retry(self, response: str) -> bool:
        normalized = response.strip().lower()
        if not normalized.startswith(("sorry", "apologies")):
            return False

        grade_or_difficulty_markers = [
            "grade level",
            "too advanced",
            "too difficult",
            "too complex",
            "too young",
            "beyond",
        ]
        refusal_markers = ["cannot help", "can't help"]
        return any(marker in normalized for marker in grade_or_difficulty_markers + refusal_markers)

    def _build_context(self, history: List[Dict[str, str]]) -> str:
        context = "Conversation history:\n"
        for msg in history[-6:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            context += f"{role}: {msg['content']}\n"
        return context

    def _get_summary_history(self, session_id: str, scope: str) -> Tuple[List[Dict[str, Any]], str]:
        if scope == "topic":
            topic_history = self.conversation_manager.get_latest_topic_thread(session_id)
            if topic_history:
                return topic_history, "topic"
        return self.conversation_manager.get_summary_source_history(session_id), "conversation"

    def _format_summary_history(self, history: List[Dict[str, Any]]) -> str:
        lines = []
        for msg in history:
            role = "User" if msg["role"] == "user" else self._assistant_summary_label(msg.get("meta") or {})
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)

    def _assistant_summary_label(self, meta: Dict[str, Any]) -> str:
        kind = meta.get("kind")
        if kind == "rejected":
            reason = meta.get("reason") or "rejected"
            return f"Assistant [rejected: {reason}]"
        if kind in {"valid_math", "valid_history"}:
            return f"Assistant [{kind}]"
        if kind == "grade_info":
            return "Assistant [grade_info]"
        if kind == "chit_chat":
            return "Assistant [chit_chat]"
        if kind == "summarize":
            scope = meta.get("summary_scope") or "conversation"
            return f"Assistant [summarize:{scope}]"
        if kind == "practice":
            category = meta.get("category") or "unknown"
            return f"Assistant [practice:{category}]"
        if kind == "clarification":
            return "Assistant [clarification]"
        return "Assistant"

    def _summary_target_label(self, scope: str) -> str:
        return "latest topic thread" if scope == "topic" else "conversation"

    def _build_summary_scope_instructions(self, scope: str) -> str:
        if scope == "topic":
            return (
                "- Focus only on the latest accepted math/history thread.\n"
                "- Do not mention older accepted topics or unrelated rejected turns.\n"
                "- Keep the summary tied to the current topic."
            )

        return (
            "- Summarize the full session, not just the latest topic.\n"
            "- If a turn is labeled `Assistant [rejected: ...]`, mention it briefly as a rejected request.\n"
            "- Keep rejected turns concise and focus mainly on accepted tutoring content."
        )

    def _build_summary_fallback(self, history: List[Dict[str, Any]], scope: str) -> Dict[str, Any]:
        topics = self._extract_topics_simple(history)
        rejected_reasons = []
        for msg in history:
            meta = msg.get("meta") or {}
            if meta.get("kind") == "rejected":
                reason = meta.get("reason") or "rejected"
                if reason not in rejected_reasons:
                    rejected_reasons.append(reason)

        if scope == "topic":
            summary = (
                f"The latest topic focused on {topics[-1]}."
                if topics
                else f"The latest topic thread contains {len(history)} messages."
            )
        else:
            topic_phrase = ", ".join(topics) if topics else "no clear topics"
            summary = f"The conversation covered {topic_phrase}."
            if rejected_reasons:
                summary += f" Some requests were rejected ({', '.join(rejected_reasons)})."

        return {
            "summary": summary,
            "topics_discussed": topics,
            "unanswered_questions": [],
        }

    def _extract_topics_simple(self, history: List[Dict[str, Any]]) -> List[str]:
        topics: List[str] = []
        keywords = {
            "math": ["equation", "math", "solve", "calculus", "algebra", "proof"],
            "history": ["history", "president", "war", "dynasty", "revolution", "emperor"],
        }

        for msg in history:
            meta = msg.get("meta") or {}
            kind = meta.get("kind")
            if kind == "valid_math" and "math" not in topics:
                topics.append("math")
            if kind == "valid_history" and "history" not in topics:
                topics.append("history")

            content = msg.get("content", "").lower()
            for topic, words in keywords.items():
                if any(word in content for word in words) and topic not in topics:
                    topics.append(topic)

        return topics


answer_generator = AnswerGenerator()
