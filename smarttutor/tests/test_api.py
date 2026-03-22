import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient


def test_health_endpoint():
    from app.main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_chat_endpoint_returns_reason(monkeypatch):
    from app.main import app

    client = TestClient(app)

    def fake_process_message(message: str, session_id: str | None = None):
        return {
            "response": "2",
            "session_id": session_id or "session-1",
            "category": "valid_math",
            "intent": "ask_question",
            "reason": "math_homework",
        }

    monkeypatch.setattr("app.main.orchestrator.process_message", fake_process_message)
    response = client.post("/chat", json={"message": "x+1=2", "session_id": "session-1"})

    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "2"
    assert data["reason"] == "math_homework"


def test_summary_endpoint_returns_structured_summary(monkeypatch):
    from app.main import app

    client = TestClient(app)

    monkeypatch.setattr(
        "app.main.answer_generator.generate_summary",
        lambda session_id: {
            "summary": "We discussed a math problem.",
            "topics_discussed": ["math"],
            "unanswered_questions": [],
        },
        raising=False,
    )
    monkeypatch.setattr(
        "app.main.conversation_manager.get_grade",
        lambda session_id: "first-year university student",
    )

    response = client.get("/conversation/session-1/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "We discussed a math problem."
    assert data["topics_discussed"] == ["math"]
    assert data["user_grade"] == "first-year university student"
