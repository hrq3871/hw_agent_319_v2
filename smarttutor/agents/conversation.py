"""
Conversation state management for SmartTutor.
"""

import re
import time
import uuid
from typing import Any, Dict, List, Optional


class ConversationManager:
    """Manage multi-turn sessions and lightweight user state."""

    SUBJECT_KINDS = {"valid_math", "valid_history"}

    FOLLOW_UP_PATTERNS = [
        r"^and more\??$",
        r"^explain more\??$",
        r"^tell me more\??$",
        r"^more details?\??$",
        r"^can you elaborate\??$",
        r"^go on\??$",
        r"^continue\??$",
        r"^what else\??$",
        r"^why\??$",
        r"^how\??$",
        r"^how so\??$",
        r"^when\??$",
        r"^what year\??$",
        r"^and then\??$",
        r"^还有呢\??$",
        r"^再多说一点\??$",
        r"^解释更多\??$",
        r"^展开讲讲\??$",
        r"^然后呢\??$",
        r"^为什么\??$",
    ]

    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.grade_patterns = [
            (r"小学生|小学\s*生|小学|primary school|elementary school", "primary school student"),
            (
                r"大学\s*一\s*年级|大学一年级|大一|first[- ]year university|first year university|university year\s*1|year\s*1 university|freshman",
                "first-year university student",
            ),
            (
                r"大学\s*二\s*年级|大学二年级|大二|second[- ]year university|second year university|university year\s*2|year\s*2 university|sophomore",
                "second-year university student",
            ),
            (
                r"大学\s*三\s*年级|大学三年级|大三|third[- ]year university|third year university|university year\s*3|year\s*3 university|junior",
                "third-year university student",
            ),
            (
                r"大学\s*四\s*年级|大学四年级|大四|fourth[- ]year university|fourth year university|university year\s*4|year\s*4 university|senior",
                "fourth-year university student",
            ),
            (
                r"高中\s*一\s*年级|高中一年级|高一|first[- ]year high school|first year high school|high school year\s*1",
                "first-year high school student",
            ),
            (
                r"高中\s*二\s*年级|高中二年级|高二|second[- ]year high school|second year high school|high school year\s*2",
                "second-year high school student",
            ),
            (
                r"高中\s*三\s*年级|高中三年级|高三|third[- ]year high school|third year high school|high school year\s*3",
                "third-year high school student",
            ),
            (r"研究生|研一|研二|研三|postgraduate|graduate student", "postgraduate student"),
            (r"博士|phd|doctoral student", "doctoral student"),
            (r"i am.*student|我是.*学生", "student"),
        ]

    def create_session(self, session_id: Optional[str] = None) -> str:
        """Create a new session, or initialize a provided session id."""
        session_id = session_id or str(uuid.uuid4())
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "messages": [],
                "grade": None,
                "created_at": time.time(),
                "last_response_kind": None,
                "last_summary_scope": None,
                "active_learning_context": None,
                "last_rejection_info": None,
            }
        return session_id

    def _ensure_session(self, session_id: str) -> Dict[str, Any]:
        self.create_session(session_id)
        return self.sessions[session_id]

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.sessions.get(session_id)

    def add_message(self, session_id: str, role: str, content: str, meta: Optional[Dict[str, Any]] = None):
        session = self._ensure_session(session_id)
        session["messages"].append(
            {
                "role": role,
                "content": content,
                "timestamp": time.time(),
                "meta": dict(meta or {}),
            }
        )

    def update_last_message_meta(
        self,
        session_id: str,
        meta: Optional[Dict[str, Any]],
        role: Optional[str] = None,
    ):
        session = self._ensure_session(session_id)
        if not session["messages"]:
            return

        last_message = session["messages"][-1]
        if role and last_message["role"] != role:
            return

        last_message.setdefault("meta", {})
        if meta:
            last_message["meta"].update(meta)

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        session = self.get_session(session_id)
        if not session:
            return []

        return [{"role": msg["role"], "content": msg["content"]} for msg in session["messages"]]

    def get_raw_history(self, session_id: str) -> List[Dict[str, Any]]:
        session = self.get_session(session_id)
        if not session:
            return []

        return [
            {
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": msg["timestamp"],
                "meta": dict(msg.get("meta") or {}),
            }
            for msg in session["messages"]
        ]

    def get_grade(self, session_id: str) -> Optional[str]:
        session = self.get_session(session_id)
        if not session:
            return None
        return session.get("grade")

    def set_grade(self, session_id: str, grade: str):
        session = self._ensure_session(session_id)
        session["grade"] = grade

    def get_last_response_kind(self, session_id: str) -> Optional[str]:
        session = self.get_session(session_id)
        if not session:
            return None
        return session.get("last_response_kind")

    def set_last_response_kind(self, session_id: str, kind: Optional[str]):
        session = self._ensure_session(session_id)
        session["last_response_kind"] = kind

    def get_last_summary_scope(self, session_id: str) -> Optional[str]:
        session = self.get_session(session_id)
        if not session:
            return None
        return session.get("last_summary_scope")

    def set_last_summary_scope(self, session_id: str, scope: Optional[str]):
        session = self._ensure_session(session_id)
        session["last_summary_scope"] = scope

    def get_active_learning_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self.get_session(session_id)
        if not session:
            return None

        context = session.get("active_learning_context")
        return dict(context) if context else None

    def set_active_learning_context(
        self,
        session_id: str,
        category: str,
        source_user_message: str,
        source_assistant_message: str,
    ):
        session = self._ensure_session(session_id)
        session["active_learning_context"] = {
            "category": category,
            "source_user_message": source_user_message,
            "source_assistant_message": source_assistant_message,
            "updated_turn": len(session["messages"]),
        }

    def get_last_rejection_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self.get_session(session_id)
        if not session:
            return None

        rejection = session.get("last_rejection_info")
        return dict(rejection) if rejection else None

    def set_last_rejection_info(
        self,
        session_id: str,
        reason: Optional[str],
        assistant_message: str,
        user_message: Optional[str] = None,
    ):
        session = self._ensure_session(session_id)
        session["last_rejection_info"] = {
            "reason": reason or "guardrail_rejected",
            "assistant_message": assistant_message,
            "user_message": user_message,
            "updated_turn": len(session["messages"]),
        }

    def clear_last_rejection_info(self, session_id: str):
        session = self._ensure_session(session_id)
        session["last_rejection_info"] = None

    def build_triage_context(self, session_id: str) -> Dict[str, Any]:
        return {
            "last_response_kind": self.get_last_response_kind(session_id),
            "last_summary_scope": self.get_last_summary_scope(session_id),
            "active_learning_context": self.get_active_learning_context(session_id),
            "last_rejection_info": self.get_last_rejection_info(session_id),
        }

    def extract_grade_from_message(self, message: str) -> Optional[str]:
        normalized_message = message.lower().strip()
        if "小学生" in message or "小学" in message:
            return "primary school student"
        if "primary school" in normalized_message or "elementary school" in normalized_message:
            return "primary school student"

        for pattern, grade in self.grade_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return grade
        return None

    def is_grade_info(self, message: str) -> bool:
        return self.extract_grade_from_message(message) is not None

    def looks_like_contextual_followup(self, message: str) -> bool:
        normalized_message = message.lower().strip()
        if not normalized_message:
            return False

        if len(normalized_message.split()) <= 3:
            if normalized_message in {"more", "more?", "details", "details?", "why", "why?", "how", "how?"}:
                return True

        return any(re.search(pattern, normalized_message, re.IGNORECASE) for pattern in self.FOLLOW_UP_PATTERNS)

    def get_summary_source_history(self, session_id: str) -> List[Dict[str, Any]]:
        return [msg for msg in self.get_raw_history(session_id) if not self._is_summary_message(msg)]

    def get_latest_topic_thread(self, session_id: str) -> List[Dict[str, Any]]:
        history = self.get_summary_source_history(session_id)
        thread: List[Dict[str, Any]] = []
        target_kind: Optional[str] = None

        for message in reversed(history):
            meta = message.get("meta") or {}
            kind = meta.get("kind")

            if target_kind is None:
                if message["role"] == "assistant" and kind in self.SUBJECT_KINDS:
                    target_kind = kind
                    thread.append(message)
                continue

            if message["role"] == "assistant":
                if kind == target_kind:
                    thread.append(message)
                    continue
                break

            thread.append(message)

        return list(reversed(thread))

    def _is_summary_message(self, message: Dict[str, Any]) -> bool:
        meta = message.get("meta") or {}
        return (
            meta.get("kind") == "summarize"
            or meta.get("intent") == "summarize"
            or meta.get("action") == "handle_summarize"
            or meta.get("action") == "summarized"
        )

    def format_history_for_llm(self, session_id: str, max_messages: int = 10) -> str:
        session = self.get_session(session_id)
        if not session:
            return ""

        lines = []
        for msg in session["messages"][-max_messages:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)

    def clear_session(self, session_id: str):
        self.sessions.pop(session_id, None)

    def cleanup_old_sessions(self, max_age_seconds: int = 3600):
        current_time = time.time()
        expired_ids = [
            session_id
            for session_id, session in self.sessions.items()
            if current_time - session["created_at"] > max_age_seconds
        ]
        for session_id in expired_ids:
            del self.sessions[session_id]


conversation_manager = ConversationManager()
