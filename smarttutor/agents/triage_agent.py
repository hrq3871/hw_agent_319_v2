"""
Triage agent for routing SmartTutor requests.
"""

import re
from typing import Any, Dict, Optional

from agents.multi_model_client import multi_model_client
from app.prompts import TRIAGE_AGENT_PROMPT


class TriageAgent:
    """Classify user input by subject and intent."""

    SIMPLE_CHITCHAT_PATTERNS = {
        "gratitude": {
            "thanks",
            "thank you",
            "thankyou",
            "thats helpful thank you",
            "that was helpful thank you",
            "谢谢",
            "多谢",
        },
        "greeting": {
            "hi",
            "hello",
            "hey",
            "你好",
        },
        "farewell": {
            "bye",
            "goodbye",
            "see you",
            "再见",
        },
    }

    FOLLOW_UP_CUES = {
        "more",
        "deeper",
        "continue",
        "continuing",
        "explain",
        "elaborate",
        "expand",
        "detail",
        "details",
        "examples",
        "example",
        "shorter",
        "concise",
        "why",
        "how",
        "again",
        "further",
        "deeper",
    }

    FOLLOW_UP_PHRASES = {
        "go on",
        "what else",
        "how so",
        "what do you mean",
        "make it shorter",
        "make it briefer",
        "more concise",
        "say something more",
        "tell me more",
        "go deeper",
        "再讲一点",
        "再说一点",
        "再多说一点",
        "解释更多",
        "展开讲讲",
    }

    CONTEXT_REFERENCES = {
        "this",
        "that",
        "it",
        "those",
        "them",
        "these",
        "he",
        "she",
        "they",
        "this topic",
        "this question",
        "这个",
        "这个话题",
        "这个问题",
    }

    PRACTICE_MARKERS = {
        "exercise",
        "exercises",
        "practice",
        "practice question",
        "practice questions",
        "practice problem",
        "practice problems",
        "practice quiz",
        "quiz",
        "quizzes",
        "worksheet",
        "worksheets",
        "练习",
        "练习题",
    }

    def __init__(self):
        self.llm_client = multi_model_client
        self.system_prompt = TRIAGE_AGENT_PROMPT

    async def classify(self, question: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        fast_path = self._fast_path_classification(question, context)
        if fast_path:
            return fast_path

        try:
            result = self.llm_client.structured_output(
                message=self._build_triage_message(question, context),
                system_prompt=self.system_prompt,
                task="triage",
                format_json=True,
            )
            return self._normalize_classification(question, result, context)
        except Exception as exc:
            print(f"Triage classification error: {exc}")
            return self._fallback_classification(question, context)

    def classify_sync(self, question: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        fast_path = self._fast_path_classification(question, context)
        if fast_path:
            return fast_path

        try:
            result = self.llm_client.structured_output(
                message=self._build_triage_message(question, context),
                system_prompt=self.system_prompt,
                task="triage",
                format_json=True,
            )
            return self._normalize_classification(question, result, context)
        except Exception as exc:
            print(f"Triage classification error: {exc}")
            return self._fallback_classification(question, context)

    def _fast_path_classification(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Resolve high-confidence cases locally to avoid an unnecessary triage LLM call."""
        subject_rescue = self._detect_subject_rescue(question)
        special = self._detect_special_intent(question, context=context, subject_rescue=subject_rescue)

        if special:
            if special.get("action") == "handle_summarize":
                return self._normalize_summary_scope(special, question, special)
            return special

        if subject_rescue:
            return subject_rescue

        return None

    def _build_triage_message(self, question: str, context: Optional[Dict[str, Any]] = None) -> str:
        if not context:
            return question

        active_context = context.get("active_learning_context")
        rejection = context.get("last_rejection_info")

        lines = [
            f"Current user message:\n{question}",
            "",
            "Conversation context:",
            f"- Last response kind: {context.get('last_response_kind') or 'none'}",
            f"- Last summary scope: {context.get('last_summary_scope') or 'none'}",
        ]

        if active_context:
            lines.extend(
                [
                    "- Active learning context: available",
                    f"- Active category: {active_context.get('category')}",
                    f"- Recent accepted user question: {active_context.get('source_user_message', '')}",
                    f"- Recent accepted assistant answer: {active_context.get('source_assistant_message', '')}",
                ]
            )
        else:
            lines.append("- Active learning context: none")

        if rejection:
            lines.extend(
                [
                    "- Recent rejection: available",
                    f"- Recent rejection reason: {rejection.get('reason')}",
                    f"- Recent rejection message: {rejection.get('assistant_message', '')}",
                ]
            )
        else:
            lines.append("- Recent rejection: none")

        return "\n".join(lines)

    def _normalize_classification(
        self,
        question: str,
        result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if "error" in result:
            return self._fallback_classification(question, context)

        normalized_result = self._normalize_summary_scope(result, question)
        subject_rescue = self._detect_subject_rescue(question)

        if normalized_result.get("action") == "handle_practice_request" and subject_rescue:
            normalized_result["category"] = subject_rescue["category"]

        result_action = normalized_result.get("action")
        result_category = normalized_result.get("category", "invalid")

        special = self._detect_special_intent(question, context=context, subject_rescue=subject_rescue)
        if special:
            special_action = special.get("action")
            if special_action == "handle_summarize":
                if result_action == "handle_summarize":
                    return self._normalize_summary_scope(normalized_result, question, special)
                return special

            if special_action == "handle_practice_request" and result_action != "handle_practice_request":
                return special

            if special_action == "handle_follow_up":
                if result_action == "handle_follow_up":
                    return normalized_result
                if result_category == "invalid" and result_action not in {
                    "handle_summarize",
                    "handle_grade_info",
                    "handle_practice_request",
                }:
                    return special

            if special_action == "handle_grade_info" and result_action != "handle_grade_info":
                return special

            if (
                special_action == "respond_chitchat"
                and result_category == "invalid"
                and normalized_result.get("intent") != "chit_chat"
            ):
                return special

        if result_category == "invalid" and subject_rescue:
            return subject_rescue

        return normalized_result

    def _fallback_classification(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fallback classification for explicit intents and obvious subject cases."""
        subject_rescue = self._detect_subject_rescue(question)
        special = self._detect_special_intent(question, context=context, subject_rescue=subject_rescue)
        if special:
            return special

        if subject_rescue:
            return subject_rescue

        return {
            "category": "invalid",
            "intent": "ask_question",
            "reason": "Unable to identify the question type.",
            "action": "respond_rejection",
        }

    def get_simple_chitchat_kind(self, message: str) -> Optional[str]:
        normalized_message = self._normalize_for_matching(message)
        for kind, patterns in self.SIMPLE_CHITCHAT_PATTERNS.items():
            if normalized_message in patterns:
                return kind
        return None

    def _normalize_summary_scope(
        self,
        result: Dict[str, Any],
        question: str,
        special: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized = dict(result)
        if normalized.get("action") != "handle_summarize":
            normalized.pop("summary_scope", None)
            return normalized

        special = special or self._detect_summary_request(question)
        summary_scope = normalized.get("summary_scope")
        if summary_scope not in {"conversation", "topic"}:
            summary_scope = (special or {}).get("summary_scope", "conversation")
        normalized["summary_scope"] = summary_scope
        return normalized

    def _detect_special_intent(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        subject_rescue: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        return (
            self._detect_summary_request(question)
            or self._detect_practice_request(question, subject_rescue=subject_rescue)
            or self._detect_follow_up(question, context=context, subject_rescue=subject_rescue)
            or self._detect_grade_info(question, subject_rescue=subject_rescue)
            or self._detect_simple_chitchat(question)
        )

    def _detect_simple_chitchat(self, question: str) -> Optional[Dict[str, Any]]:
        chitchat_kind = self.get_simple_chitchat_kind(question)
        if chitchat_kind is None:
            return None

        reasons = {
            "gratitude": "Detected simple gratitude.",
            "greeting": "Detected simple greeting.",
            "farewell": "Detected simple farewell.",
        }
        return {
            "category": "invalid",
            "intent": "chit_chat",
            "reason": reasons[chitchat_kind],
            "action": "respond_chitchat",
        }

    def _detect_grade_info(
        self,
        question: str,
        subject_rescue: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        question_lower = question.lower()
        grade_patterns = [
            "大一",
            "大二",
            "大三",
            "大四",
            "高一",
            "高二",
            "高三",
            "小学生",
            "小学",
            "primary school",
            "elementary school",
            "first-year university student",
            "second-year university student",
            "third-year university student",
            "fourth-year university student",
            "first year university",
            "second year university",
            "third year university",
            "fourth year university",
            "freshman",
            "sophomore",
            "junior",
            "senior",
            "first-year high school",
            "second-year high school",
            "third-year high school",
            "graduate student",
            "postgraduate",
            "doctoral student",
            "phd",
            "年级",
            "学生",
            "我是",
            "grade",
            "student",
            "i am",
        ]
        grade_score = sum(1 for keyword in grade_patterns if keyword in question_lower)

        if grade_score > 0 and not subject_rescue:
            return {
                "category": "invalid",
                "intent": "grade_info",
                "reason": "The user is sharing grade information.",
                "action": "handle_grade_info",
            }

        return None

    def _detect_practice_request(
        self,
        question: str,
        subject_rescue: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        normalized_question = self._normalize_for_matching(question)
        if not self._looks_like_practice_request(normalized_question):
            return None

        return {
            "category": subject_rescue["category"] if subject_rescue else "invalid",
            "intent": "practice_request",
            "reason": "The user is asking for practice questions.",
            "action": "handle_practice_request",
        }

    def _detect_follow_up(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        subject_rescue: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if subject_rescue:
            return None

        if not context:
            return None

        if not (
            context.get("active_learning_context")
            or context.get("last_rejection_info")
            or context.get("last_response_kind") == "summarize"
        ):
            return None

        normalized_question = self._normalize_for_matching(question)
        if not self._looks_like_contextual_followup(normalized_question):
            return None

        return {
            "category": "invalid",
            "intent": "follow_up",
            "reason": "The user is asking a context-dependent follow-up.",
            "action": "handle_follow_up",
        }

    def _looks_like_practice_request(self, normalized_question: str) -> bool:
        if not normalized_question:
            return False

        return self._contains_any_phrase(normalized_question, self.PRACTICE_MARKERS)

    def _looks_like_contextual_followup(self, normalized_question: str) -> bool:
        if not normalized_question:
            return False

        if self._contains_any_phrase(normalized_question, self.FOLLOW_UP_PHRASES):
            return True

        words = normalized_question.split()
        word_set = set(words)
        if len(words) <= 8 and (word_set & self.FOLLOW_UP_CUES):
            return True

        if len(words) <= 6 and (word_set & self.CONTEXT_REFERENCES):
            return True

        return False

    def _detect_subject_rescue(self, question: str) -> Optional[Dict[str, Any]]:
        question_lower = question.lower()
        math_keywords = [
            "计算",
            "求解",
            "方程",
            "函数",
            "几何",
            "代数",
            "微积分",
            "微分",
            "积分",
            "概率",
            "统计",
            "等于",
            "根号",
            "平方根",
            "证明",
            "定理",
            "math",
            "calculus",
            "solve",
            "equation",
            "derivative",
            "integral",
            "algebra",
            "geometry",
            "probability",
            "statistics",
            "rational",
            "square root",
            "distance",
            "proof",
            "prove",
            "theorem",
        ]
        history_keywords = [
            "历史",
            "总统",
            "皇帝",
            "战争",
            "朝代",
            "年代",
            "人物",
            "事件",
            "革命",
            "第一任",
            "谁是",
            "哪一年",
            "history",
            "president",
            "emperor",
            "war",
            "dynasty",
            "event",
            "historical",
            "revolution",
            "who was",
            "what year",
            "when did",
        ]
        math_score = sum(1 for keyword in math_keywords if keyword in question_lower)
        history_score = sum(1 for keyword in history_keywords if keyword in question_lower)

        equation_patterns = [
            r"\b[xyz]\s*=\s*[-+]?\d+",
            r"\b[xyz]\s*[+\-*/]\s*[-+]?\d+",
            r"[-+]?\d+\s*[+\-*/=]\s*[-+]?\d+",
            r"\bx\^?\d",
            r"sqrt\s*\(",
        ]
        math_score += sum(1 for pattern in equation_patterns if re.search(pattern, question_lower))

        if math_score > history_score and math_score > 0:
            return {
                "category": "valid_math",
                "intent": "ask_question",
                "reason": "Detected clear math-related keywords.",
                "action": "handoff_to_math",
            }

        if history_score > math_score and history_score > 0:
            return {
                "category": "valid_history",
                "intent": "ask_question",
                "reason": "Detected clear history-related keywords.",
                "action": "handoff_to_history",
            }

        return None

    def _detect_summary_request(self, question: str) -> Optional[Dict[str, Any]]:
        normalized_question = self._normalize_for_matching(question)
        summary_verbs = [
            "summarize",
            "summarise",
            "summary",
            "recap",
            "conclude",
            "wrap up",
            "sum up",
            "总结",
            "概括",
            "归纳",
        ]
        conversation_targets = [
            "conversation",
            "our conversation",
            "this conversation",
            "conversation so far",
            "chat",
            "our chat",
            "this chat",
            "chat so far",
            "dialogue",
            "dialog",
            "discussion",
            "对话",
            "聊天",
            "会话",
        ]
        topic_targets = [
            "this topic",
            "this question",
            "this problem",
            "this subject",
            "这个话题",
            "这个问题",
            "这个题目",
        ]

        has_summary_verb = self._contains_any_phrase(normalized_question, summary_verbs)
        if not has_summary_verb:
            return None

        if self._contains_any_phrase(normalized_question, conversation_targets):
            return {
                "category": "invalid",
                "intent": "summarize",
                "reason": "The user is asking for a conversation summary.",
                "action": "handle_summarize",
                "summary_scope": "conversation",
            }

        if self._contains_any_phrase(normalized_question, topic_targets):
            return {
                "category": "invalid",
                "intent": "summarize",
                "reason": "The user is asking for a summary of the current topic.",
                "action": "handle_summarize",
                "summary_scope": "topic",
            }

        return None

    def _contains_any_phrase(self, text: str, phrases) -> bool:
        return any(self._contains_phrase(text, phrase) for phrase in phrases)

    def _contains_phrase(self, text: str, phrase: str) -> bool:
        normalized_phrase = self._normalize_for_matching(phrase)
        if not normalized_phrase:
            return False
        if re.search(r"[\u4e00-\u9fff]", normalized_phrase):
            return normalized_phrase in text
        return f" {normalized_phrase} " in f" {text} "

    def _normalize_for_matching(self, text: str) -> str:
        normalized = text.lower().strip().replace("’", "'").replace("'", "")
        normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized


triage_agent = TriageAgent()
