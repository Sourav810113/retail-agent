---
title: 'US-101 — Order lookup, health check and lookup audit'
type: 'feature'
created: '2026-11-10'
status: 'in-review'
route: 'dispatch'
baseline_commit: '6a3e4e93f8af99a86d8d1581e7235158f7e81307'
review_loop_iteration: 0
context: ['{project-root}/docs/stories/US-101.md', '{project-root}/docs/architecture.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The repo has planning docs only; there is no app. Customers cannot look up an Order, support has no audit trail, and later stories have no skeleton to build on.

**Approach:** Implement docs/stories/US-101.md exactly as written, following docs/architecture.md (AD-1…AD-11): the layered skeleton, `GET /orders/{order_id}`, `GET /healthz`, the AD-8 error model, `ORDER_LOOKUP` audit events and seed data. Also add `requirements.txt` with pinned versions (user request), run pytest with coverage in `.venv`, and fix failures. Do not commit — the user reviews and commits.

## Boundaries & Constraints

**Always:**
- Python 3.12 from `.venv`; versions pinned exactly per the architecture Stack table (verified resolvable: fastapi 0.162.2, pydantic 2.14.3, uvicorn 0.54.0, pytest 9.2.0, pytest-cov 7.1.0, httpx 0.28.1, pip-audit 2.10.1, bandit 1.9.4).
- Relative imports inside `src/retail_agent`; tests import `src.retail_agent...` (AD-11).
- Every DB access inside `UnitOfWork.transaction()`; only entry-point service methods open one (AD-3).
- Audit before raise; the not-found event commits, then `NotFoundError` is raised (AD-4).
- Email: header `X-Customer-Email`, `strip().lower()`, never logged/audited/echoed/returned (AD-7).
- Money as INTEGER cents in SQLite, 2dp string in JSON, conversion only via `domain/money.py` (AD-5).
- Time only via `core/clock.py`; `format_ts` → `YYYY-MM-DDTHH:MM:SS.ffffffZ` (AD-6).

**Never:**
- No `returns`/`return_lines` tables, no return endpoints (US-102+).
- No Dockerfile or CI workflow (US-104).
- No `.env`, no `pydantic-settings`, no `EmailStr`.
- No git commit.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Delivered lookup | `ORD-1001`, header `Asha@Example.com ` | 200 OrderView; `return_eligible_until` = delivery + 30; `quantity_returned` 0; `returns` []; no email in body | audit `found` |
| Shipped lookup | shipped Order, correct email | 200, `delivery_date` and `return_eligible_until` null | audit `found` |
| Unknown ID / wrong email | either | identical 404 `NOT_FOUND` "Order not found" | audit `not_found` with supplied `order_id` |
| Missing / empty header | no `X-Customer-Email` | 422 `INVALID_REQUEST`, message from `loc`+`type` only | not audited |
| Health failure | `HealthService.check()` raises | 503 `UNHEALTHY` | — |
| Framework errors | unknown path / wrong method / unexpected exception | 404 / 405 / 500 in `{"error":{...}}` | 500 carries no request data |

</frozen-after-approval>

## Code Map

Greenfield: no source exists. `.venv` (Python 3.12.16, uv 0.13.7) is empty. `.gitignore` already covers `.venv`, `.coverage`, `.env*`. Do not touch `docs/` planning files other than adding the QA gate.

- `pyproject.toml`, `uv.lock`, `requirements.txt` -- deps + `[tool.uv] package = false`, pytest `pythonpath=["."]`, cov addopts (story task 11); `requirements.txt` exported from the lock so the two agree.
- `src/retail_agent/core/{clock,db,settings}.py` -- Clock/SystemClock/FixedClock/format_ts; connection factory + `UnitOfWork`; constants (`RETURN_WINDOW_DAYS = 30`).
- `src/retail_agent/domain/{enums,models,errors,money,audit_details}.py` -- pure, stdlib + Pydantic only.
- `src/retail_agent/repositories/{schema.sql,seed.py,order_repository.py,audit_repository.py,return_repository.py}` -- four tables; seed offsets from `clock.today()`; `returned_quantities` stub returns `{}`.
- `src/retail_agent/services/{audit_service,order_service,health_service}.py`.
- `src/retail_agent/api/{schemas,errors,deps,orders,health}.py`; `src/retail_agent/main.py`.
- `tests/unit/`, `tests/api/`, `tests/test_architecture.py`, `tests/conftest.py`.
- `docs/qa/gates/US-101.yml` -- QA gate.

## Tasks & Acceptance

**Execution:**
- [x] `pyproject.toml`, `uv.lock`, `requirements.txt` -- scaffold and pin; install into `.venv` -- story task 1, user request
- [x] `src/retail_agent/core/*` -- clock, db/UoW, settings -- tasks 2–3
- [x] `src/retail_agent/repositories/*` -- schema, seed, repositories -- tasks 4, 6
- [x] `src/retail_agent/domain/*` -- enums, models, errors, money, audit details (all five) -- task 5
- [x] `src/retail_agent/services/*` -- audit, order, health -- task 7
- [x] `src/retail_agent/api/*`, `main.py` -- routers, schemas, handlers, deps, `create_app` -- tasks 8–9
- [x] `tests/**` -- unit (lookup, email normalization, UoW, money, clock), API (AC-1…AC-7), audit rows (AC-5), architecture AST scan (AC-8) -- task 10
- [ ] `docs/qa/gates/US-101.yml` -- PASS only once every AC is verified -- task 12

**Acceptance Criteria:**
- Given the story's AC-1…AC-8, when `pytest` runs, then all pass and domain+services coverage ≥ 90%.
- Given `uvicorn src.retail_agent.main:app --port 8000`, when started, then `/healthz` returns 200 and `/docs` loads.

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Design Notes

Seed (offsets from T = `clock.today()`): `ORD-1001` delivered T−12 (asha@example.com, includes a qty-2 line), `ORD-1002` delivered T−45, `ORD-1003` shipped, `ORD-1004` cancelled; `SKU-GIFTCARD` has `returnable = 0`. Offsets documented in `seed.py`'s docstring.

Unexpected-exception 500 needs Starlette's `ServerErrorMiddleware` path: register a handler for `Exception` and test with `TestClient(app, raise_server_exceptions=False)`.

## Verification

**Commands:**
- `.venv/bin/python -m pytest` -- expected: all pass, coverage gate ≥ 90%
- `.venv/bin/python -m uvicorn src.retail_agent.main:app --port 8000` then `curl localhost:8000/healthz` -- expected: `{"status":"ok"}`
