# SmartTutor - Specification Document

## Project Overview

**Project Name:** SmartTutor - Multi-turn Homework Tutoring Agent
**Branch:** `feat/reliability-guardrails-polish`
**Focus:** Reliability and Guardrails for LLM-based tutoring system

### Project Objective
Design and implement a reliable multi-turn homework tutoring agent that:
- Accepts genuine math and history homework questions
- Rejects questions outside the intended scope
- Behaves consistently across multi-turn conversations

## Functionality Specification

### Core Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Math Question Answering | Algebra, calculus, geometry, probability, etc. | P0 |
| History Question Answering | Historical events, figures, periods, dates | P0 |
| Guardrails | Explicit rejection rules for non-homework/inappropriate content | P0 |
| Multi-turn Conversation | Context continuation for follow-up questions | P0 |
| Conversation Summary | On-demand conversation summarization | P1 |
| Grade Adaptation | Adapt explanations based on user grade level | P1 |
| Practice Questions | Generate topic-aligned exercises | P1 |
| Simple Chit-chat | Handle greetings and polite expressions | P2 |

### User Interactions and Flows

#### Flow 1: Math Question Answering
1. User submits a math question
2. Triage agent classifies as `valid_math`
3. Guardrail agent checks for explicit rule violations
4. Answer generator produces grade-adapted response
5. Response stored in session for multi-turn support

#### Flow 2: History Question Answering
1. User submits a history question
2. Triage agent classifies as `valid_history`
3. Guardrail agent checks for explicit rule violations
4. Answer generator produces grade-adapted response
5. Response stored in session for multi-turn support

#### Flow 3: Rejection Flow
1. User submits non-homework question
2. Triage agent classifies as `invalid`
3. Guardrail agent provides rejection reason
4. Polite rejection message returned
5. Rejection info stored for potential follow-up explanations

#### Flow 4: Grade Information Collection
1. User shares grade level
2. Triage agent identifies `grade_info` intent
3. Grade stored in session
4. Future answers adapted to grade level

#### Flow 5: Conversation Summary
1. User requests summary
2. Orchestrator routes to answer generator
3. Summary generated from conversation history
4. Structured summary returned (summary + topics + unanswered questions)

### Data Handling

- **Session Storage:** In-memory dictionary (`conversation_manager.sessions`)
- **Session Data:** Messages, grade, last response kind, active learning context
- **Session Cleanup:** Automatic cleanup for sessions older than 1 hour

### Edge Cases

| Edge Case | Handling |
|-----------|----------|
| Short follow-ups (`And more?`) | Context inheritance from previous valid response |
| Low grade + advanced topic | Simplified explanation instead of rejection |
| Model unavailable | Automatic fallback to default model |
| Invalid triage output | Deterministic fallback rules |
| Travel/local questions | Explicit guardrail rejection |
| Dangerous content | Immediate rejection via guardrail |

## Architecture

### Active Agent Pipeline

```
User Input
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                     Orchestrator                             │
│  (Single decision-making entry point for API and UI)        │
└─────────────────────────┬───────────────────────────────────┘
                          │
    ┌─────────────────────┼─────────────────────┐
    ▼                     ▼                     ▼
┌───────────┐      ┌──────────────┐      ┌─────────────────┐
│  Triage   │ ───▶ │   Guardrail  │ ───▶ │ Answer Generator│
│   Agent   │      │    Agent     │      │                 │
└───────────┘      └──────────────┘      └─────────────────┘
      │                   │                      │
      │ Grade info         │ Reject reasons       │ Responses
      │ Summary request     │                     │
      │ Chit-chat          │                     │
      ▼                   ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  Conversation Manager                        │
│         (Session state, history, grade, context)             │
└─────────────────────────────────────────────────────────────┘
```

### Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `orchestrator.py` | Central routing, action dispatch, context inheritance |
| `triage_agent.py` | Fast-path classification, LLM-based triage, fallback rules |
| `guardrail_agent.py` | Explicit rule checks, LLM-based validation |
| `answer_generator.py` | Subject prompts, summaries, practice questions |
| `conversation.py` | Session state, history, grade management |

## Acceptance Criteria

### Must Pass (P0)

- [x] `x+1=2` is accepted as valid math and solved correctly
- [x] `Who was the first president of France?` is accepted as valid history
- [x] `How do I get to London?` is rejected as non-homework
- [x] `Who was HKUST's first president?` is rejected as too local
- [x] `What would happen if someone throws a firecracker on a busy street?` is rejected
- [x] Multi-turn follow-ups continue previous context
- [x] Grade information is remembered and used for adaptation
- [x] Conversation summary request returns structured summary

### Should Pass (P1)

- [x] Short follow-ups (`And more?`, `Why?`) work correctly
- [x] Practice question generation works
- [x] Simple chit-chat (`Hi`, `Thank you`) is handled politely
- [x] Low-grade students can ask advanced topics (with simplification)
- [x] Rejected questions followed by "why" get explanation

### Test Coverage

| Test File | Coverage |
|-----------|----------|
| `tests/test_examples.py` | Core routing, guardrails, special intents |
| `tests/test_multiturn_followups.py` | Multi-turn behavior, context inheritance |
| `tests/test_fallback_rules.py` | Fallback classification, Chinese compatibility |
| `tests/test_ui.py` | UI delegates to orchestrator |
| `test_api.py` | API response consistency |
| `test_agents.py` | Model fallback, retry logic |

## Validation Results

**Automated Tests:** 37 passed (March 21, 2026)
**Manual Smoke Test:** All scenarios pass

See `VALIDATION.md` for detailed validation evidence.

## Submission Requirements Checklist

| Requirement | File | Status |
|-------------|------|--------|
| Max 2-page PDF report | `smarttutor/REPORT.md` (base) | ⚠️ Create |
| Source code | `smarttutor/` | ✅ Ready |
| 1-minute demo recording | N/A | External |

## Project Structure

```
smarttutor/
├── agents/
│   ├── orchestrator.py      # Central routing
│   ├── triage_agent.py      # Question classification
│   ├── guardrail_agent.py   # Scope/safety checks
│   ├── answer_generator.py  # Response generation
│   ├── conversation.py      # Session management
│   └── multi_model_client.py # Model routing
├── app/
│   ├── main.py              # FastAPI entry
│   ├── prompts.py           # Prompt templates
│   └── models.py            # Data models
├── ui/
│   └── gradio_app.py        # Gradio interface
├── tests/
│   ├── test_examples.py
│   ├── test_fallback_rules.py
│   ├── test_multiturn_followups.py
│   ├── test_api.py
│   ├── test_agents.py
│   ├── test_ui.py
│   ├── TESTING.md
│   └── VALIDATION.md
├── requirements.txt
└── README.md
```

## Recent Commits

| Commit | Description |
|--------|-------------|
| `02f3f1e` | docs: rewrite english agent documentation and report |
| `85eeee7` | fix: narrow chit-chat bypass and simplify demo dialogue |
| `129209f` | docs: add end-to-end dialogue smoke test |
| `11642ff` | fix: allow simple chit-chat without rejection |
| `ed70eb7` | fix: carry context across short follow-up prompts |
| `75a5ec1` | feat: switch default UX to English |
| `1ef6e94` | fix: handle advanced math across grade levels |
| `8ffd8fd` | test: cover primary school advanced math scenario |
