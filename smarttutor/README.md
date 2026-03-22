# SmartTutor

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-orange.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Gradio-4.0+-pink.svg" alt="Gradio">
  <img src="https://img.shields.io/badge/Focus-Reliability%20%26%20Guardrails-green.svg" alt="Project Focus">
</p>

## Overview

SmartTutor is a multi-turn homework tutoring agent built around a small, reliability-focused agent pipeline. Its supported academic scope is intentionally narrow: **math** and **history** homework. The system is designed to do three things well:

1. accept genuine math and history homework questions,
2. reject questions that should not be answered, and
3. behave consistently across multi-turn conversation.

The current implementation prioritizes predictable routing, explicit guardrails, and testable behavior over broad subject coverage.

## What the Agent Is Supposed to Do

SmartTutor should:

- answer math homework questions such as algebra, calculus, or word problems,
- answer history homework questions about historical people, events, and time periods,
- remember conversation context so short follow-up questions continue the previous explanation,
- generate practice questions when the user asks for exercises about the current math or history topic,
- remember user grade information and adapt answer depth,
- summarize the conversation on request,
- politely reject prompts that are not math or history homework,
- reject prompts that are unsafe, too local or niche, or outside the intended scope,
- handle simple social turns such as `Hi` or `That's helpful, thank you.` without incorrectly rejecting them.

SmartTutor should **not** behave like a general assistant. It is a homework tutor with explicit boundaries.

## Active Agent Design

The active system is centered on the following components:

- `orchestrator`: the single decision-making entry point used by the app,
- `conversation_manager`: stores session history, grade level, and lightweight dialogue state,
- `triage_agent`: classifies the current message,
- `guardrail_agent`: decides whether the question should be refused,
- `answer_generator`: produces subject answers and summaries,
- `multi_model_client`: routes tasks to configured models and applies model fallback.

### End-to-End Decision Flow

The current active flow is:

1. The user message is added to the current session.
2. `triage_agent` classifies the message into `valid_math`, `valid_history`, or `invalid`, and also identifies intents such as `summarize`, `grade_info`, or `chit_chat`.
3. `orchestrator` checks whether the message should inherit context from the previous successful turn. This is what allows short follow-ups such as `And more?` to continue a history answer.
4. Special intents are handled before guardrails:
   - grade sharing updates the stored user level,
   - summary requests trigger summary generation,
   - practice requests generate topic-aligned exercises,
   - simple chit-chat receives a short polite response.
5. For normal questions, `guardrail_agent` applies scope and safety checks.
6. If accepted, `answer_generator` builds the subject prompt, includes recent conversation context, and generates the response.
7. The final response is stored back into the session for future turns.

### Why This Design Is Reliable

The design emphasizes reliability in several ways:

- **Single active routing path**: both the API and the UI rely on the orchestrator, so behavior stays consistent.
- **Separation of concerns**:
  - triage decides what the message is,
  - guardrails decide whether it should be answered,
  - answer generation decides how to explain it.
- **Deterministic fallbacks**: obvious prompts can still be handled correctly even if the model output is too strict or malformed.
- **Context repair for short follow-ups**: short, under-specified messages can inherit the previous valid subject when appropriate.
- **Model fallback**: if a task-specific model is unavailable, the client can fall back to the default model instead of failing immediately.
- **Grade-aware simplification**: advanced topics are not automatically rejected for younger users; the system tries to explain them more simply.

## Guardrails and Boundary Rules

The guardrail design is intentionally explicit.

### Accepted Scope

Accepted questions are limited to:

- math homework,
- history homework,
- concept explanations within math or history,
- follow-up questions that clearly continue a previous accepted explanation.

### Rejected Scope

Rejected questions include:

- non-homework requests such as travel, weather, shopping, or general life advice,
- subjects outside math and history,
- overly local or niche prompts such as campus-specific leadership trivia,
- unsafe or inappropriate prompts.

### Bilingual Compatibility

The default user-facing experience is English, but internal fallback rules still preserve Chinese compatibility for:

- grade statements,
- summary requests,
- obvious math/history keywords,
- simple guardrail cases.

This means the system can present itself in English without breaking Chinese input support.

## Multi-Turn Behavior

SmartTutor is designed as a multi-turn tutor rather than a one-shot classifier.

It currently supports:

- short contextual follow-ups such as `Why subtract 1 on both sides?`,
- short history follow-ups such as `And more?`,
- contextual exercise requests such as `Give me 3 practice questions about this`,
- summary refinement turns,
- grade updates mid-conversation,
- non-academic social turns such as greeting, thanks, and goodbye.

The conversation manager stores:

- recent dialogue history,
- the current user grade,
- the type of the last successful response.

That lightweight state is enough to support the core multi-turn behaviors required by the assignment without introducing a database or a more complex memory system.

## Reliability Validation

The project does not rely only on prompts. It is backed by automated checks and manual smoke tests.

### Automated Validation

Run the test suite from the `smarttutor` directory:

```powershell
pytest -q
```

The tests cover:

- accepted math and history questions,
- rejected non-homework and too-local questions,
- follow-up continuation,
- contextual practice-question generation,
- summary requests,
- grade adaptation,
- low-grade advanced-math handling,
- polite chit-chat handling,
- API field consistency,
- model fallback behavior,
- UI orchestrator delegation.

### Manual Smoke Test

Use the following short demo sessions:

```text
Assistant: Welcome to SmartTutor, your homework tutor for math and history. What can I help you with today?

Session A: accepted questions, follow-up, and practice

User: Hi
Assistant: A brief greeting. It should not reject the message.

User: x+1=2
Assistant: Accept as math and solve it.

User: Why subtract 1 on both sides?
Assistant: Continue the same math context instead of rejecting the follow-up.

User: Give me 3 practice questions about this.
Assistant: Generate three related math practice questions with short hints.

User: Who was the first president of France?
Assistant: Accept as history and answer correctly.

User: And more?
Assistant: Continue the previous history context rather than rejecting the short follow-up.

Session B: rejected questions

User: How do I get to London?
Assistant: Reject because this is travel advice, not math or history homework.

User: Who was HKUST's first president?
Assistant: Reject because it is too local or niche for the intended history-homework scope.

Session C: grade adaptation and summary

User: I am a primary school student.
Assistant: Store the grade level.

User: What is the derivative of x^2?
Assistant: Do not reject. Give a simpler explanation suitable for a younger student.

User: That's helpful, thank you.
Assistant: You're welcome.

User: Summarize our conversation so far.
Assistant: Return a concise conversation summary.
```

This scenario is short enough for a report or demo, while still demonstrating:

- two accepted cases,
- two rejected cases,
- one contextual practice-generation case,
- one summary request,
- contextual follow-up handling,
- low-grade advanced-topic handling,
- polite chit-chat handling.

For detailed validation evidence and requirement-to-test mapping, see `tests/VALIDATION.md`.

## Minimal Run Instructions

Install dependencies:

```powershell
cd smarttutor
pip install -r requirements.txt
```

Set the required environment variables in `.env`:

```env
HKUST_AZURE_API_KEY=your_api_key_here
HKUST_AZURE_ENDPOINT=https://hkust.azure-api.net
HKUST_AZURE_API_VERSION=2025-02-01-preview

MATH_MODEL=gpt-4o-mini
HISTORY_MODEL=gpt-4o
DEFAULT_MODEL=gpt-4o-mini
```

Start the web interface:

```powershell
python -m ui.gradio_app
```

Open:

```text
the local URL shown in the terminal, usually http://127.0.0.1:7861
```

Optional API server:

```powershell
python -m app.main
```

API docs:

```text
http://127.0.0.1:8000/docs
```

## Agent-Focused Repository Map

Only the most important agent files are listed here:

```text
smarttutor/
├── agents/
│   ├── orchestrator.py
│   ├── conversation.py
│   ├── triage_agent.py
│   ├── guardrail_agent.py
│   ├── answer_generator.py
│   └── multi_model_client.py
├── app/
│   ├── prompts.py
│   ├── models.py
│   └── main.py
├── ui/
│   └── gradio_app.py
└── tests/
    ├── test_examples.py
    ├── test_fallback_rules.py
    ├── test_multiturn_followups.py
    ├── test_api.py
    ├── test_agents.py
    └── test_ui.py
```

Legacy files such as `classifier.py`, `guardrails.py`, and `expert_agents.py` are still present in the repository, but the active tutoring pipeline described above is the one used for the current project deliverable.
