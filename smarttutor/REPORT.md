# SmartTutor: A Reliable Multi-Turn Homework Tutoring Agent

**Course Project Report**  
**Group Members:** `[Name 1]`, `[Name 2]`, `[Name 3]`

## 1. Goal

SmartTutor is a multi-turn homework tutoring agent designed for a narrow academic scope: **math** and **history**. The project focus is not breadth, but **reliability and guardrails**. The system should answer valid homework questions, reject questions that are outside scope or inappropriate, preserve multi-turn context, adapt to user grade level, generate practice questions when appropriate, and summarize the conversation when asked.

Our design goal is: **accept the right questions, reject the wrong ones, and do so consistently across turns**.

## 2. Agent Design

The active system uses a small agent pipeline instead of a single unconstrained prompt. The main modules are:

- `orchestrator`: the only decision-making entry point,
- `conversation_manager`: stores session history, user grade, and lightweight dialogue state,
- `triage_agent`: classifies the current user turn,
- `guardrail_agent`: checks whether the question should be answered,
- `answer_generator`: produces math/history answers, summaries, and practice questions,
- `multi_model_client`: selects the configured model and supports fallback.

The flow is:

1. store the user message in the session,
2. classify the message,
3. repair context for short follow-ups when needed,
4. handle special intents such as grade sharing, summary, practice requests, or simple chit-chat,
5. apply guardrails,
6. generate the answer if accepted,
7. store the final response for future turns.

This separation is important for reliability. Classification, refusal, and answer generation are treated as different responsibilities, so the system is easier to test and debug.

## 3. Reliability and Guardrails

The system is intentionally conservative. It only answers math and history homework. It rejects:

- non-homework prompts such as travel advice,
- questions outside math and history,
- overly local or niche prompts,
- unsafe or inappropriate prompts.

To make the behavior more reliable, we do not depend on the LLM alone. We also use:

- **deterministic fallback rules** for obvious cases,
- **context carry-over** for short follow-up turns such as `And more?`,
- **context-aware practice generation** for requests such as `Give me 3 practice questions about this`,
- **grade memory** so later answers can be adapted,
- **model fallback** if a task-specific model is unavailable,
- **simplified retry** when a valid advanced topic is asked by a younger student.

The default user-facing language is English, but Chinese keyword compatibility is preserved in internal fallback rules. This avoids breaking Chinese inputs while keeping the interface and outputs consistent for the report and demo.

## 4. How We Validate It

We use two layers of validation.

First, we use automated tests. The current suite checks accepted questions, rejected questions, summary, follow-up behavior, contextual practice generation, low-grade advanced math, polite chit-chat, API consistency, and fallback behavior. This helps us show that the system is not working only by chance in one demo.

Second, we use a short manual smoke test across a few compact sessions. This checks the exact multi-turn behavior that the assignment emphasizes: accepted homework questions, rejected non-homework questions, follow-up continuation, contextual exercise generation, grade adaptation, and summary.

## 5. Validation Examples

| User input | Expected behavior | Observed result |
|---|---|---|
| `x+1=2` | Accepted as math | The system solves the equation and explains the steps. |
| `Give me 3 practice questions about this.` after a solved math turn | Generate contextual exercises | The system generates math practice questions aligned with the previous accepted topic. |
| `Who was the first president of France?` | Accepted as history | The system answers with Louis-Napoleon Bonaparte and related context. |
| `How do I get to London?` | Rejected as non-homework | The system refuses because it is not a math or history homework question. |
| `Who was HKUST's first president?` | Rejected as too local/niche | The system refuses as outside the intended general history-homework scope. |
| `Summarize our conversation so far.` | Return a conversation summary | The system returns a structured summary of the conversation. |
| `And more?` after a history answer | Continue prior context | The system continues the previous history explanation instead of rejecting the short follow-up. |
| `I am a primary school student.` then `What is the derivative of x^2?` | Do not reject; simplify | The system gives a simplified explanation rather than refusing only because the topic is advanced. |
| `That's helpful, thank you.` | Do not reject | The system replies politely with `You're welcome.` |

These examples cover the minimum assignment requirements and also highlight the boundary cases that we specifically engineered for reliability, including contextual tutoring actions beyond direct question answering.

## 6. Minimal Run Instructions

From the `smarttutor` directory:

```powershell
pip install -r requirements.txt
python -m ui.gradio_app
```

Then open the local URL shown in the terminal, usually `http://127.0.0.1:7861`.

If the API server is also needed:

```powershell
python -m app.main
```

Then open `http://127.0.0.1:8000/docs`.

The required API credentials and model names are configured through `.env`.

## 7. Conclusion

SmartTutor is not intended to be a general chatbot. It is a focused homework tutoring agent with explicit boundaries. Its main contribution is not simply answering math and history questions, but doing so with a small, testable architecture that supports multi-turn tutoring, reliable refusal behavior, grade-aware explanations, practice generation, and summary. This gives a stronger answer to the assignment question: not only what the agent should do, but also how we can justify that it is doing the right thing.
