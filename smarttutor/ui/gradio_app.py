"""
Gradio UI for SmartTutor.
"""

import os
import sys
from typing import List, Optional, Tuple

try:
    import gradio as gr
except ImportError:  # pragma: no cover - optional for test environments
    gr = None

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.conversation import conversation_manager
from agents.orchestrator import orchestrator


session_id: Optional[str] = None


def init_session() -> str:
    global session_id
    session_id = conversation_manager.create_session()
    return session_id


def chat(message: str, history: List) -> Tuple[str, List]:
    global session_id

    if not message.strip():
        return "", history

    history = history or []
    if session_id is None:
        session_id = init_session()

    history.append([message, "Thinking..."])

    try:
        result = orchestrator.process_message(message=message, session_id=session_id)
        session_id = result.get("session_id", session_id)
        history[-1][1] = result["response"]
    except Exception as exc:
        history[-1][1] = f"Error: {exc}"

    return "", history


def clear_history() -> Tuple[str, List]:
    init_session()
    return "", []


def greet() -> str:
    return "Welcome to SmartTutor. I can help with math and history homework questions."


def _resolve_server_port() -> Optional[int]:
    raw_port = os.getenv("GRADIO_SERVER_PORT")
    if raw_port is None or not raw_port.strip():
        return None
    return int(raw_port)


def _resolve_server_name() -> str:
    raw_name = os.getenv("GRADIO_SERVER_NAME")
    if raw_name is None or not raw_name.strip():
        return "127.0.0.1"
    return raw_name.strip()


def build_demo():
    if gr is None:
        raise RuntimeError("gradio is not installed")

    with gr.Blocks(title="SmartTutor") as demo:
        gr.Markdown("# SmartTutor")
        gr.Markdown("Your homework tutor for math and history questions.")

        chatbot = gr.Chatbot(label="Conversation", height=500)
        msg_input = gr.Textbox(
            label="Question",
            placeholder="For example: x+1=2, Who was the first president of France?",
        )

        with gr.Row():
            submit_btn = gr.Button("Send", variant="primary")
            clear_btn = gr.Button("Clear")

        gr.Markdown("### Example Questions")
        gr.Markdown("- x+1=2")
        gr.Markdown("- Who was the first president of France?")
        gr.Markdown("- I am a first-year university student")
        gr.Markdown("- Summarize our conversation")

        submit_btn.click(chat, [msg_input, chatbot], [msg_input, chatbot])
        msg_input.submit(chat, [msg_input, chatbot], [msg_input, chatbot])
        clear_btn.click(clear_history, outputs=[msg_input, chatbot])

    return demo


demo = build_demo() if gr is not None else None


if __name__ == "__main__":
    if demo is None:
        raise SystemExit("gradio is not installed")

    init_session()
    demo.launch(
        server_name=_resolve_server_name(),
        server_port=_resolve_server_port(),
        show_api=False,
        share=False,
    )
