"""
Data models for SmartTutor.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class QuestionCategory(str, Enum):
    """Enumeration of supported question categories."""
    VALID_MATH = "valid_math"
    VALID_HISTORY = "valid_history"
    INVALID = "invalid"


class UserIntent(str, Enum):
    """Enumeration of supported user intents."""
    ASK_QUESTION = "ask_question"
    SUMMARIZE = "summarize"
    GRADE_INFO = "grade_info"
    CHIT_CHAT = "chit_chat"
    FOLLOW_UP = "follow_up"
    PRACTICE_REQUEST = "practice_request"


class ChatRequest(BaseModel):
    """Request payload for a chat turn."""
    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(None, description="Session ID")


class ChatResponse(BaseModel):
    """Response payload returned by the chat endpoint."""
    response: str = Field(..., description="Assistant response")
    session_id: str = Field(..., description="Session ID")
    category: str = Field(..., description="Question category")
    intent: str = Field(..., description="User intent")
    reason: Optional[str] = Field(None, description="Classification reason")


class ConversationSummary(BaseModel):
    """Summary payload for a conversation."""
    session_id: str
    summary: str
    topics_discussed: list[str]
    user_grade: Optional[str]


class ConversationHistoryItem(BaseModel):
    """Single item in the stored conversation history."""
    role: str
    content: str
    timestamp: float
