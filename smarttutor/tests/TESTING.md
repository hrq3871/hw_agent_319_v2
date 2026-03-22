# Testing Notes

This folder contains behavior-focused tests for SmartTutor.

## Test Files

| File | Coverage |
|------|----------|
| `test_examples.py` | Core routing, guardrails, special intents |
| `test_fallback_rules.py` | Fallback classification, Chinese compatibility |
| `test_multiturn_followups.py` | Multi-turn follow-ups, context inheritance |
| `test_api.py` | API endpoints, response consistency |
| `test_agents.py` | Model fallback, retry logic, session management |
| `test_ui.py` | UI delegation to the orchestrator |

## Documentation

| File | Description |
|------|-------------|
| `TESTING.md` | This file - quick reference for running tests |
| `VALIDATION.md` | Detailed validation evidence and requirement mapping |

## How to Run Tests

From the `smarttutor` directory:

```powershell
pytest -q
```

Run only the tests in this folder:

```powershell
pytest -q tests
```

Run a specific test file:

```powershell
pytest -q tests/test_examples.py
pytest -q tests/test_multiturn_followups.py
```

## Notes

- Most tests are mock-first, so they do not spend API tokens.
- Tests mainly verify routing, guardrails, session flow, and response policy.
- See `VALIDATION.md` for detailed validation evidence and requirement coverage.
