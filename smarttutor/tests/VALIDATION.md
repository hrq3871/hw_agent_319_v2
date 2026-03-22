# SmartTutor Validation

## Purpose

This document explains how SmartTutor was validated and what evidence supports the claim that the system meets the assignment goals on branch `feat/reliability-guardrails-polish`.

The validation strategy is intentionally simple and reproducible:

- automated regression tests for routing, guardrails, context handling, and fallback behavior,
- a short manual smoke test for the exact multi-turn behaviors emphasized by the assignment.

## Validation Baseline

- Active branch: `feat/reliability-guardrails-polish`
- Verification date: March 22, 2026
- Test result: 37 tests available in this directory
- Validation mode: mock-first tests plus a small real manual smoke test

This is not a claim that SmartTutor is a general-purpose tutor. It is evidence that the current system behaves correctly on the narrow homework-tutor scope required by the project.

## What We Need to Prove

For this project, the main question is not only "does it answer something?" but "how do we know it answers and refuses correctly?"

We need evidence for these behaviors:

- valid `math` questions are accepted,
- valid `history` questions are accepted,
- non-homework or unsafe questions are rejected,
- overly local or niche questions are rejected,
- short follow-up turns continue previous accepted context,
- grade information is remembered and later answers are simplified when needed,
- conversation summary works,
- simple polite chit-chat is not incorrectly rejected,
- UI and API both use the same active orchestrator path,
- fallback rules prevent brittle failures when the model output is too strict or unavailable.

## Requirement-to-Evidence Map

| Requirement | Automated evidence | Manual smoke evidence | Status |
|---|---|---|---|
| Accept valid math homework | `test_examples.py`, `test_fallback_rules.py` | `x+1=2` | Passed |
| Accept valid history homework | `test_examples.py`, `test_fallback_rules.py` | `Who was the first president of France?` | Passed |
| Reject non-homework prompts | `test_examples.py`, `test_fallback_rules.py` | `How do I get to London?` | Passed |
| Reject too-local or niche prompts | `test_examples.py`, `test_fallback_rules.py` | `Who was HKUST's first president?` | Passed |
| Continue multi-turn follow-ups | `test_multiturn_followups.py` | `Why subtract 1 on both sides?`, `And more?` | Passed |
| Preserve grade info and adapt explanation | `test_examples.py`, `test_multiturn_followups.py`, `test_fallback_rules.py` | `I am a primary school student.` then `What is the derivative of x^2?` | Passed |
| Summarize the conversation | `test_examples.py`, `test_api.py` | `Summarize our conversation so far.` | Passed |
| Handle simple polite chit-chat without false rejection | `test_examples.py` | `Hi`, `That's helpful, thank you.` | Passed |
| Keep UI and API behavior aligned | `test_ui.py`, `test_api.py` | Indirectly covered by demo flow | Passed |
| Recover from reliability edge cases | `test_agents.py`, `test_fallback_rules.py` | Reflected in stable demo behavior | Passed |

## Automated Validation

Run from the `smarttutor` directory:

```powershell
pytest -q
```

### What the automated suite covers

- `test_examples.py`
  - accepted math and history examples,
  - rejected non-homework and too-local prompts,
  - special handling for `grade_info` and `summarize`,
  - polite chit-chat handling,
  - guardrail behavior when triage labels are imperfect.
- `test_multiturn_followups.py`
  - math and history follow-up continuation,
  - clarification after an initial rejection,
  - summary follow-up refinement,
  - short follow-up repair such as `And more?`,
  - low-grade advanced-math behavior.
- `test_fallback_rules.py`
  - deterministic fallback classification for obvious prompts,
  - Chinese compatibility for grade and summary inputs,
  - rescue when LLM triage is too strict,
  - explicit travel and too-local guardrail rules.
- `test_api.py`
  - `/chat` returns `reason`,
  - summary endpoint returns structured summary data.
- `test_agents.py`
  - missing sessions are created automatically,
  - model fallback works when the math model is unavailable,
  - answer generation retries when a younger student asks an advanced but still valid math question.
- `test_ui.py`
  - Gradio UI delegates to the orchestrator instead of using a separate path.

### Why these tests matter

These tests are behavior-focused. Most of them are mock-first, which keeps token use low while still verifying routing, guardrails, session state, and response policy. This is the right level of evidence for a course project whose main goal is reliable multi-turn behavior, not open-domain factual benchmarking.

## Manual Smoke Test

Automated tests show policy consistency. The manual smoke test shows that the full user-visible flow works in one conversation.

Use one session and send the following turns in order:

```
User: Hi
Expected: brief greeting, no rejection

User: x+1=2
Expected: accepted as math

User: Why subtract 1 on both sides?
Expected: continues the previous math explanation

User: Who was the first president of France?
Expected: accepted as history

User: And more?
Expected: continues the previous history context

User: How do I get to London?
Expected: rejected as non-homework

User: Who was HKUST's first president?
Expected: rejected as too local or niche

User: I am a primary school student.
Expected: grade is stored

User: What is the derivative of x^2?
Expected: accepted, but explained more simply

User: That's helpful, thank you.
Expected: polite reply, no rejection

User: Summarize our conversation so far.
Expected: concise summary of the session
```

## Why This Counts as Evidence

This validation is credible for the assignment because it combines:

- repeatable automated checks,
- requirement-oriented manual scenarios,
- direct coverage of both accepted and rejected paths,
- coverage of edge cases that previously failed,
- documentation that connects expected behavior to observed behavior.

In other words, the project does not ask the reader to trust a single happy-path demo. It provides regression tests for the policy and a compact manual script for the end-to-end interaction.

## Limits of the Validation

This document does not claim:

- broad factual coverage across all math and history topics,
- benchmark-level evaluation against a large labeled dataset,
- production-grade safety guarantees,
- exhaustive real-model testing on every prompt variation.

What it does claim is narrower and more defensible: for the scope required by the homework, the current SmartTutor pipeline has explicit evidence that it accepts the right kinds of questions, rejects the wrong ones, and behaves consistently across turns.

## Reproduction

Install dependencies and run the checks from `smarttutor`:

```powershell
pip install -r requirements.txt
pytest -q
python -m ui.gradio_app
```

Then open `http://127.0.0.1:7861` and replay the manual smoke-test dialogue above.
