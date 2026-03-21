"""Central request routing for SmartTutor."""

import re
from typing import Any, Dict, Optional, Tuple

from agents.answer_generator import answer_generator
from agents.conversation import conversation_manager
from agents.guardrail_agent import guardrail_agent
from agents.triage_agent import triage_agent
from app.prompts import REJECTION_TEMPLATES


class AgentOrchestrator:
    """Coordinate triage, guardrails, summaries, follow-ups, and practice."""

    SUBJECT_KINDS = {"valid_math", "valid_history"}

    def __init__(self):
        self.conversation_manager = conversation_manager
        self.triage_agent = triage_agent
        self.guardrail_agent = guardrail_agent
        self.answer_generator = answer_generator

    def process_message(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        session_id = session_id or self.conversation_manager.create_session()
        grade = self.conversation_manager.get_grade(session_id)

        self.conversation_manager.add_message(session_id, "user", message)
        triage_context = self.conversation_manager.build_triage_context(session_id)
        classification = self.triage_agent.classify_sync(message, context=triage_context)
        classification = self._apply_followup_context(classification, message, triage_context, session_id)
        self._record_user_classification(session_id, classification)

        action = classification.get("action")
        reason = classification.get("reason")
        summary_scope = classification.get("summary_scope")

        if action == "handle_grade_info":
            return self._handle_grade_info(message, session_id, reason)

        if action == "handle_summarize":
            return self._handle_summarize(session_id, reason, summary_scope)

        if action == "handle_practice_request":
            return self._handle_practice_request(message, session_id, grade, classification, triage_context)

        if action == "handle_follow_up":
            return self._handle_follow_up(message, session_id, grade, classification, triage_context)

        if action == "respond_chitchat" or (
            classification.get("intent") == "chit_chat" and self._looks_like_simple_chit_chat(message)
        ):
            return self._handle_chit_chat(message, session_id, reason)

        return self._handle_standard_question(message, session_id, grade, classification)

    async def process_message_async(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        session_id = session_id or self.conversation_manager.create_session()
        grade = self.conversation_manager.get_grade(session_id)

        self.conversation_manager.add_message(session_id, "user", message)
        triage_context = self.conversation_manager.build_triage_context(session_id)
        classification = await self.triage_agent.classify(message, context=triage_context)
        classification = self._apply_followup_context(classification, message, triage_context, session_id)
        self._record_user_classification(session_id, classification)

        action = classification.get("action")
        reason = classification.get("reason")
        summary_scope = classification.get("summary_scope")

        if action == "handle_grade_info":
            return self._handle_grade_info(message, session_id, reason)

        if action == "handle_summarize":
            return self._handle_summarize(session_id, reason, summary_scope)

        if action == "handle_practice_request":
            return self._handle_practice_request(message, session_id, grade, classification, triage_context)

        if action == "handle_follow_up":
            return self._handle_follow_up(message, session_id, grade, classification, triage_context)

        if action == "respond_chitchat" or (
            classification.get("intent") == "chit_chat" and self._looks_like_simple_chit_chat(message)
        ):
            return self._handle_chit_chat(message, session_id, reason)

        return await self._handle_standard_question_async(message, session_id, grade, classification)

    def _handle_standard_question(
        self,
        message: str,
        session_id: str,
        grade: Optional[str],
        classification: Dict[str, Any],
    ) -> Dict[str, Any]:
        category = classification.get("category", "invalid")
        reason = classification.get("reason")
        intent = classification.get("intent", "ask_question")

        if category in self.SUBJECT_KINDS:
            should_reject, rejection_message = self.guardrail_agent.check_explicit_rules(message)
        else:
            should_reject, rejection_message = self.guardrail_agent.check_sync(message)

        if should_reject:
            return self._record_rejection(
                session_id=session_id,
                message=message,
                rejection_message=rejection_message,
                reason=reason or "guardrail_rejected",
                intent=intent,
                action="rejected",
            )

        if category == "valid_math":
            return self._generate_subject_answer(
                message=message,
                session_id=session_id,
                grade=grade,
                classification=classification,
                resolved_category="valid_math",
            )

        if category == "valid_history":
            return self._generate_subject_answer(
                message=message,
                session_id=session_id,
                grade=grade,
                classification=classification,
                resolved_category="valid_history",
            )

        return self._record_rejection(
            session_id=session_id,
            message=message,
            rejection_message=REJECTION_TEMPLATES["default"],
            reason=reason or "invalid_request",
            intent=intent,
            action="rejected",
        )

    async def _handle_standard_question_async(
        self,
        message: str,
        session_id: str,
        grade: Optional[str],
        classification: Dict[str, Any],
    ) -> Dict[str, Any]:
        category = classification.get("category", "invalid")
        reason = classification.get("reason")
        intent = classification.get("intent", "ask_question")

        if category in self.SUBJECT_KINDS:
            should_reject, rejection_message = self.guardrail_agent.check_explicit_rules(message)
        else:
            should_reject, rejection_message = await self.guardrail_agent.check(message)

        if should_reject:
            return self._record_rejection(
                session_id=session_id,
                message=message,
                rejection_message=rejection_message,
                reason=reason or "guardrail_rejected",
                intent=intent,
                action="rejected",
            )

        if category == "valid_math":
            return self._generate_subject_answer(
                message=message,
                session_id=session_id,
                grade=grade,
                classification=classification,
                resolved_category="valid_math",
            )

        if category == "valid_history":
            return self._generate_subject_answer(
                message=message,
                session_id=session_id,
                grade=grade,
                classification=classification,
                resolved_category="valid_history",
            )

        return self._record_rejection(
            session_id=session_id,
            message=message,
            rejection_message=REJECTION_TEMPLATES["default"],
            reason=reason or "invalid_request",
            intent=intent,
            action="rejected",
        )

    def _handle_grade_info(
        self,
        message: str,
        session_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        extracted_grade = self.conversation_manager.extract_grade_from_message(message)

        if extracted_grade:
            self.conversation_manager.set_grade(session_id, extracted_grade)
            response_text = (
                f"Thanks. I've recorded your grade level as {extracted_grade}. "
                "I'll tailor future math or history answers to that level."
            )
        else:
            response_text = (
                "Thanks. I've noted that information. "
                "You can continue with a math or history homework question."
            )

        self.conversation_manager.set_last_response_kind(session_id, "grade_info")
        self.conversation_manager.add_message(
            session_id,
            "assistant",
            response_text,
            meta={
                "kind": "grade_info",
                "intent": "grade_info",
                "reason": reason or "grade_info",
                "action": "grade_info_collected",
            },
        )
        return {
            "response": response_text,
            "session_id": session_id,
            "category": "invalid",
            "intent": "grade_info",
            "reason": reason or "grade_info",
            "action": "grade_info_collected",
        }

    def _handle_summarize(
        self,
        session_id: str,
        reason: Optional[str] = None,
        summary_scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        scope = summary_scope or "conversation"
        summary_result = self.answer_generator.generate_summary(session_id, scope=scope)
        topics = summary_result.get("topics_discussed", [])
        response_text = (
            f"Conversation summary:\n{summary_result.get('summary', '')}\n\n"
            f"Topics discussed: {', '.join(topics) if topics else 'none'}"
        )

        self.conversation_manager.set_last_response_kind(session_id, "summarize")
        self.conversation_manager.set_last_summary_scope(session_id, scope)
        self.conversation_manager.add_message(
            session_id,
            "assistant",
            response_text,
            meta={
                "kind": "summarize",
                "intent": "summarize",
                "reason": reason or "summarize",
                "summary_scope": scope,
                "action": "summarized",
            },
        )
        return {
            "response": response_text,
            "session_id": session_id,
            "category": "invalid",
            "intent": "summarize",
            "reason": reason or "summarize",
            "action": "summarized",
        }

    def _handle_practice_request(
        self,
        message: str,
        session_id: str,
        grade: Optional[str],
        classification: Dict[str, Any],
        triage_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        resolved_category, topic_seed = self._resolve_practice_target(message, classification, triage_context)
        reason = classification.get("reason") or "practice_request"

        if resolved_category in self.SUBJECT_KINDS:
            should_reject, rejection_message = self.guardrail_agent.check_explicit_rules(message)
            if should_reject:
                return self._record_rejection(
                    session_id=session_id,
                    message=message,
                    rejection_message=rejection_message,
                    reason=reason,
                    intent="practice_request",
                    action="rejected",
                )

            count = self._extract_requested_count(message)
            response_text = self.answer_generator.generate_practice(
                category=resolved_category,
                topic_seed=topic_seed,
                grade=grade,
                count=count,
            )
            self.conversation_manager.set_last_response_kind(session_id, "practice")
            self.conversation_manager.add_message(
                session_id,
                "assistant",
                response_text,
                meta={
                    "kind": "practice",
                    "category": resolved_category,
                    "intent": "practice_request",
                    "reason": reason,
                    "action": "practice_generated",
                },
            )
            return {
                "response": response_text,
                "session_id": session_id,
                "category": resolved_category,
                "intent": "practice_request",
                "reason": reason,
                "action": "practice_generated",
            }

        should_reject, rejection_message = self.guardrail_agent.check_explicit_rules(message)
        if should_reject:
            return self._record_rejection(
                session_id=session_id,
                message=message,
                rejection_message=rejection_message,
                reason=reason,
                intent="practice_request",
                action="rejected",
            )

        return self._handle_context_clarification(
            session_id=session_id,
            intent="practice_request",
            reason=reason,
            response_text=(
                "I can generate practice questions, but I need a math or history topic first. "
                "Tell me the topic, such as algebra, derivatives, or the French Revolution."
            ),
        )

    def _handle_follow_up(
        self,
        message: str,
        session_id: str,
        grade: Optional[str],
        classification: Dict[str, Any],
        triage_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        reason = classification.get("reason") or "follow_up"
        last_response_kind = triage_context.get("last_response_kind")

        if last_response_kind == "summarize":
            return self._handle_summarize(
                session_id=session_id,
                reason=reason,
                summary_scope=triage_context.get("last_summary_scope"),
            )

        if (
            last_response_kind == "rejected"
            and triage_context.get("last_rejection_info")
            and self._looks_like_rejection_explanation_request(message)
        ):
            return self._handle_rejection_explanation(session_id, reason, triage_context["last_rejection_info"])

        resolved_category = classification.get("category")
        if resolved_category not in self.SUBJECT_KINDS:
            active_context = triage_context.get("active_learning_context") or {}
            resolved_category = active_context.get("category")

        if resolved_category in self.SUBJECT_KINDS:
            return self._generate_subject_answer(
                message=message,
                session_id=session_id,
                grade=grade,
                classification=classification,
                resolved_category=resolved_category,
            )

        return self._handle_context_clarification(
            session_id=session_id,
            intent="follow_up",
            reason=reason,
            response_text=(
                "I can continue the explanation, but I need you to name the math or history topic or question you want to continue."
            ),
        )

    def _handle_rejection_explanation(
        self,
        session_id: str,
        reason: str,
        rejection_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        prior_reason = rejection_info.get("reason") or "guardrail_rejected"
        prior_message = rejection_info.get("assistant_message") or REJECTION_TEMPLATES["default"]
        explanation = self._build_rejection_explanation(prior_reason, prior_message)

        self.conversation_manager.set_last_response_kind(session_id, "rejection_explanation")
        self.conversation_manager.add_message(
            session_id,
            "assistant",
            explanation,
            meta={
                "kind": "clarification",
                "intent": "follow_up",
                "reason": reason,
                "action": "explained_rejection",
            },
        )
        return {
            "response": explanation,
            "session_id": session_id,
            "category": "invalid",
            "intent": "follow_up",
            "reason": reason,
            "action": "explained_rejection",
        }

    def _handle_context_clarification(
        self,
        session_id: str,
        intent: str,
        reason: str,
        response_text: str,
    ) -> Dict[str, Any]:
        self.conversation_manager.set_last_response_kind(session_id, "clarification")
        self.conversation_manager.add_message(
            session_id,
            "assistant",
            response_text,
            meta={
                "kind": "clarification",
                "intent": intent,
                "reason": reason,
                "action": "clarification_requested",
            },
        )
        return {
            "response": response_text,
            "session_id": session_id,
            "category": "invalid",
            "intent": intent,
            "reason": reason,
            "action": "clarification_requested",
        }

    def _handle_chit_chat(
        self,
        message: str,
        session_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        response_text = self._build_chit_chat_response(message)
        self.conversation_manager.set_last_response_kind(session_id, "chit_chat")
        self.conversation_manager.add_message(
            session_id,
            "assistant",
            response_text,
            meta={
                "kind": "chit_chat",
                "intent": "chit_chat",
                "reason": reason or "simple_chit_chat",
                "action": "chit_chat_responded",
            },
        )
        return {
            "response": response_text,
            "session_id": session_id,
            "category": "invalid",
            "intent": "chit_chat",
            "reason": reason or "simple_chit_chat",
            "action": "chit_chat_responded",
        }

    def _generate_subject_answer(
        self,
        message: str,
        session_id: str,
        grade: Optional[str],
        classification: Dict[str, Any],
        resolved_category: str,
    ) -> Dict[str, Any]:
        if resolved_category == "valid_math":
            response_text = self.answer_generator.generate_answer(
                question=message,
                session_id=session_id,
                category="valid_math",
                grade=grade,
            )
        else:
            response_text = self.answer_generator.generate_answer(
                question=message,
                session_id=session_id,
                category="valid_history",
                grade=grade,
            )

        self.conversation_manager.set_last_response_kind(session_id, resolved_category)
        self.conversation_manager.clear_last_rejection_info(session_id)
        self.conversation_manager.set_active_learning_context(
            session_id,
            category=resolved_category,
            source_user_message=message,
            source_assistant_message=response_text,
        )
        self.conversation_manager.add_message(
            session_id,
            "assistant",
            response_text,
            meta={
                "kind": resolved_category,
                "intent": classification.get("intent", "ask_question"),
                "reason": classification.get("reason"),
                "action": "answered",
            },
        )
        return {
            "response": response_text,
            "session_id": session_id,
            "category": resolved_category,
            "intent": classification.get("intent", "ask_question"),
            "reason": classification.get("reason"),
            "action": "answered",
        }

    def _record_rejection(
        self,
        session_id: str,
        message: str,
        rejection_message: str,
        reason: str,
        intent: str,
        action: str,
    ) -> Dict[str, Any]:
        self.conversation_manager.set_last_response_kind(session_id, "rejected")
        self.conversation_manager.set_last_rejection_info(
            session_id,
            reason=reason,
            assistant_message=rejection_message,
            user_message=message,
        )
        self.conversation_manager.add_message(
            session_id,
            "assistant",
            rejection_message,
            meta={
                "kind": "rejected",
                "intent": intent,
                "reason": reason,
                "action": action,
            },
        )
        return {
            "response": rejection_message,
            "session_id": session_id,
            "category": "invalid",
            "intent": intent,
            "reason": reason,
            "action": action,
        }

    def _apply_followup_context(
        self,
        classification: Dict[str, Any],
        message: str,
        triage_context: Dict[str, Any],
        session_id: str,
    ) -> Dict[str, Any]:
        last_response_kind = triage_context.get("last_response_kind")
        if classification.get("action") == "handle_follow_up" and last_response_kind == "summarize":
            return {
                "category": "invalid",
                "intent": "summarize",
                "reason": "Treated as a follow-up refinement of the previous summary request.",
                "action": "handle_summarize",
                "summary_scope": triage_context.get("last_summary_scope") or "conversation",
            }

        if classification.get("action") in {
            "handle_grade_info",
            "handle_summarize",
            "handle_follow_up",
            "handle_practice_request",
        }:
            return classification

        if classification.get("category") in self.SUBJECT_KINDS:
            return classification

        if last_response_kind == "summarize" and self.conversation_manager.looks_like_contextual_followup(message):
            return {
                "category": "invalid",
                "intent": "summarize",
                "reason": "Treated as a follow-up refinement of the previous summary request.",
                "action": "handle_summarize",
                "summary_scope": triage_context.get("last_summary_scope") or "conversation",
            }

        if last_response_kind in self.SUBJECT_KINDS and self.conversation_manager.looks_like_contextual_followup(message):
            subject_name = "math" if last_response_kind == "valid_math" else "history"
            handoff_action = "handoff_to_math" if last_response_kind == "valid_math" else "handoff_to_history"
            return {
                "category": last_response_kind,
                "intent": "follow_up",
                "reason": f"Treated as a contextual follow-up to the previous {subject_name} answer.",
                "action": handoff_action,
            }

        return classification

    def _resolve_practice_target(
        self,
        message: str,
        classification: Dict[str, Any],
        triage_context: Dict[str, Any],
    ) -> Tuple[Optional[str], Optional[str]]:
        if classification.get("category") in self.SUBJECT_KINDS:
            return classification["category"], message

        active_context = triage_context.get("active_learning_context")
        if active_context and active_context.get("category") in self.SUBJECT_KINDS:
            topic_seed = self._build_topic_seed_from_context(active_context)
            return active_context["category"], topic_seed

        return None, None

    def _build_topic_seed_from_context(self, active_context: Dict[str, Any]) -> str:
        source_user = active_context.get("source_user_message", "").strip()
        source_assistant = active_context.get("source_assistant_message", "").strip()
        parts = []
        if source_user:
            parts.append(f"Original topic question: {source_user}")
        if source_assistant:
            parts.append(f"Recent explanation: {source_assistant}")
        return "\n".join(parts)

    def _extract_requested_count(self, message: str) -> int:
        match = re.search(r"\b([1-9]|10)\b", message)
        if match:
            return int(match.group(1))
        return 3

    def _looks_like_rejection_explanation_request(self, message: str) -> bool:
        normalized = re.sub(r"\s+", " ", message.lower()).strip()
        direct = {"why", "why?", "how", "how?"}
        if normalized in direct:
            return True
        return "why" in normalized or "how" in normalized

    def _build_rejection_explanation(self, prior_reason: str, prior_message: str) -> str:
        if prior_reason == "too_local":
            prefix = "I rejected that request because it was too local or niche for a general math or history homework question."
        elif prior_reason in {"non_homework", "travel_question"}:
            prefix = "I rejected that request because it was not a math or history homework question."
        elif prior_reason in {"out_of_scope", "programming_request"}:
            prefix = "I rejected that request because it was outside the supported math and history scope."
        else:
            prefix = "I rejected that request because it did not fit the supported homework scope."
        return f"{prefix} The previous reply was: {prior_message}"

    def _build_chit_chat_response(self, message: str) -> str:
        chitchat_kind = self.triage_agent.get_simple_chitchat_kind(message)
        if chitchat_kind == "gratitude":
            return "You're welcome."
        if chitchat_kind == "greeting":
            return "Hi. Feel free to ask a math or history homework question."
        if chitchat_kind == "farewell":
            return "Goodbye. Feel free to come back with a math or history homework question anytime."
        return "I'm here to help with math and history homework questions."

    def _looks_like_simple_chit_chat(self, message: str) -> bool:
        return self.triage_agent.get_simple_chitchat_kind(message) is not None

    def _record_user_classification(self, session_id: str, classification: Dict[str, Any]):
        self.conversation_manager.update_last_message_meta(
            session_id,
            {
                "kind": classification.get("category", "invalid"),
                "intent": classification.get("intent", "ask_question"),
                "reason": classification.get("reason"),
                "action": classification.get("action"),
                "summary_scope": classification.get("summary_scope"),
            },
            role="user",
        )


orchestrator = AgentOrchestrator()
