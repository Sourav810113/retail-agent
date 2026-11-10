---
title: Review gate — Architecture Spine, Retail Returns Assistant
reviewed: docs/architecture/architecture-retail-agent-2026-11-10/ARCHITECTURE-SPINE.md
against: docs/prd.md (+ addendum.md)
date: 2026-11-10
verdict: PASS WITH CHANGES (fix 3 high before stories start)
---

# Review Gate — Architecture Spine

**Verdict:** The spine is solid and covers every FR/NFR. Three high gaps let independently built stories produce code that clashes at runtime: nested transactions, the import root, and where INVALID_REQUEST is checked. Close those three and tighten the audit and response contracts before story work starts.

Lenses: (1) Rubric, (2) Currency, (3) Adversary. Severity: critical / high / medium / low. No critical findings.

## Coverage check (rubric)

Every FR-1…FR-15 and NFR-1…NFR-7 appears in `binds` and in the Capability map. The Deployment section covers deployment and CI. Nothing in the Deferred list lets two units diverge: auth, persistence, scaling, versioning, observability and cancellation are all out of scope or blocked outright. The gaps are in *how precisely* the covered items are pinned down, not in whether they are covered.

## High

### H1 — Nested service transactions deadlock or commit early (Adversary: ReturnService vs InventoryService / AuditService)
- **Location:** AD-3, AD-4, Capability map row FR-9/FR-10.
- **Issue:** AD-3 says "only services open a transaction" and backs `uow.transaction()` with a non-reentrant `threading.Lock`. The map puts restock in both `return_service` and `inventory_service`, and AD-4 makes `AuditService` (a service) write denial events "in its own transaction". Two stories can each obey every AD and still clash. Story A writes `InventoryService.restock()` and `AuditService.record()` so they open their own `with uow.transaction()`. Story B calls them from inside `ReturnService.request_return`'s transaction. The result is a deadlock on the Lock. With an RLock instead, the inner commit fires early, which breaks FR-9/FR-11 atomicity.
- **Fix:** Add a rule that only use-case entry points (the service methods routers call) open a transaction. Service-to-service calls, `AuditService.record` and `InventoryService.restock` never open one, and they assert that one is active (use `if not uow.in_transaction: raise`, not `assert`, so bandit B101 does not fire). The caller opens the separate denial-audit transaction. Name one mutation path for Inventory: `InventoryRepository.add_quantity`, called only from inside the return transaction. `InventoryService` is read-only (FR-10).

### H2 — Two import roots: `src.retail_agent` vs `retail_agent` (Adversary: any two stories)
- **Location:** Structural Seed (`src/` layout, `pyproject.toml`, `uv sync`), Deployment run command `uvicorn src.retail_agent.main:app`.
- **Issue:** The run command (also fixed in CLAUDE.md) imports `src.retail_agent`. `uv sync` installs the project editable, which makes `retail_agent` importable too. Story A writes `from retail_agent.domain.errors import NotFoundError` and story B writes `from src.retail_agent.domain.errors import ...`. The module then loads twice, giving two distinct `NotFoundError` and `DenialReason` classes. `api/errors.py` handlers stop matching and return 500, and enum comparisons fail. Both stories obey AD-1 and AD-10.
- **Fix:** Pick one rule and state it in Conventions. Either use relative imports only inside the package, or use absolute `src.retail_agent...` everywhere with `[tool.pytest.ini_options] pythonpath=["."]` and no installable package (`[tool.uv] package = false`). Add a CI grep or ruff `banned-module-level-imports`/TID rule that rejects the other root.

### H3 — INVALID_REQUEST placement and rule order are unfixed (Adversary: returns-request story vs audit story)
- **Location:** AD-8, FR-4/FR-5 mapping, sequence diagram.
- **Issue:** `DenialReason` includes `INVALID_REQUEST`, and AD-8 *also* maps `RequestValidationError` to `INVALID_REQUEST`. Empty lines, duplicate SKUs and quantity < 1 can therefore be checked in the Pydantic schema (`min_length=1`, `ge=1`, a validator) or in `domain/eligibility`. The two choices behave differently. In the schema, the check runs before the not-found check (FR-4 rule 1), so an unknown order with `quantity: 0` returns 422 instead of 404. No `RETURN_REQUESTED denied` audit event is written either, which breaks FR-11/UJ-2. In the domain, you get a 404 and an audit event. The order of checks across lines is also unfixed: with line 1 not returnable and line 2 not on the order, the "first rule that failed" (FR-3) depends on whether evaluation loops rule-major or line-major.
- **Fix:** Say that the schema checks only types and required fields. Empty lines, duplicate SKUs and qty < 1 are domain rules that raise `ReturnDeniedError(INVALID_REQUEST)` and are audited. Publish the exact evaluation order as an ordered list: `NotFound → empty lines → ORDER_NOT_DELIVERED → RETURN_WINDOW_EXPIRED → duplicate SKU/ITEM_NOT_ON_ORDER → ITEM_NOT_RETURNABLE → qty<1 → QUANTITY_EXCEEDS_RETURNABLE`. Each rule is evaluated over all lines before the next rule runs (rule-major).

## Medium

### M1 — Reads on the shared connection bypass the lock; sqlite3 transaction mode unspecified (Currency + Rubric)
- **Location:** AD-2, AD-3.
- **Issue:** The connection is shared (`check_same_thread=False`), and sync handlers run in a threadpool. AD-3 only locks *transactions*. A `GET /orders` or `GET /inventory` read from another thread runs on the same connection while a return transaction is open, so it sees uncommitted rows (same connection = same transaction). It also depends on SQLite's serialized threading mode, which the Python docs say the user must serialize. Python 3.12's sqlite3 defaults to legacy implicit `BEGIN`, so `with uow.transaction()` semantics depend on `isolation_level`/`autocommit`, and nothing pins them.
- **Fix:** All DB access, reads included, goes through the UnitOfWork with the lock held. Open the connection with `isolation_level=None` and have `transaction()` issue `BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK` explicitly. As an alternative, use one connection per request to `file:retail?mode=memory&cache=shared` with `uri=True`, keeping a holder connection open on `app.state`.

### M2 — Response shapes are named but not defined (Adversary: order-lookup story vs returns story)
- **Location:** API Endpoints table ("Order view", "Return view", `returns[]`, `lines`).
- **Issue:** The lookup story renders `returns[]` as `{return_id, refund, created_at}` and the returns story uses `refund_amount`. Line fields (`unit_price` vs `unit_price_paid`, `quantity` vs `quantity_purchased`) and the shape of POST `lines` are also free. Both stories also need "quantity already returned" (AD-9) and could each write their own SUM/join, since `return_lines` has no `order_id`.
- **Fix:** Add field lists for `OrderView`, `OrderLineView`, `ReturnSummary`, `ReturnView` (= POST 201 body), `InventoryView` and `AuditEventView` in `api/schemas.py` to the spine. Name one query owner, `ReturnRepository.returned_quantities(order_id) -> dict[str, int]`, used by both lookup and eligibility.

### M3 — Audit contract leaves outcome, details, event count and owner free (Adversary: returns story vs audit story)
- **Location:** AD-4, sequence diagram "audit x3".
- **Issue:** `outcome` is an untyped string, so `found`/`FOUND`/`success` can all appear. The outcome for a not-found return request is undefined (NOT_FOUND is not a DenialReason). The fields of each typed `details` model and their file are unstated (AD-10 covers only entities and enums). "audit x3" conflicts with FR-11's "each Restock": one event per Return Line, or one event listing all lines?
- **Fix:** Add a closed `Outcome` enum in `domain/enums.py` (`found`, `not_found`, `accepted`, `denied`, `recorded`). Set `RETURN_REQUESTED` not-found to `not_found`. Put the details models in `domain/audit_details.py` with their fields listed (e.g. `ReturnRequestedDetails{lines, denial_reason?}`, `RestockDetails{sku, quantity}`, `RefundDetails{amount}`). Require one `INVENTORY_RESTOCKED` per Return Line and fix the diagram to read "2 + N events".

### M4 — Audit storage format, ordering tiebreak and time filter undefined
- **Location:** Structural Seed `audit_events`, Conventions Dates/times, `GET /audit-events`.
- **Issue:** `occurred_at` is stored as text, but `isoformat()` (`+00:00`, optional microseconds) and `...Z` sort differently, which breaks `from`/`to` filtering and "newest first". Events written in one transaction (and every event under a fixed test clock) share a timestamp, and uuid4 `event_id` is not ordered, so the order is not deterministic. `from` is a Python keyword and needs `Query(alias="from")`. Whether the bounds are inclusive or exclusive, and whether they are dates or datetimes, is unstated. The ERD links `AUDIT_EVENTS` to `ORDERS`. A real FK would reject `not_found` lookups that carry an unknown `order_id`.
- **Fix:** Add `seq INTEGER PRIMARY KEY AUTOINCREMENT` and order by `occurred_at DESC, seq DESC`. Store `occurred_at` as fixed-width `YYYY-MM-DDTHH:MM:SS.ffffffZ` produced by one helper in `core/clock.py`. Make `from`/`to` ISO datetimes with `from` inclusive and `to` exclusive. State that `audit_events.order_id`/`return_id` are plain columns, not FKs.

### M5 — Not every error goes through the one error model (Rubric, NFR-1)
- **Location:** AD-8.
- **Issue:** Unknown routes (404), 405s and any `HTTPException` come from Starlette as `{"detail": ...}`, and unhandled exceptions return a plain-text 500. NFR-1 says *all* errors use `{"error":{code,message}}`.
- **Fix:** Also register handlers for `starlette.exceptions.HTTPException` (map status to `NOT_FOUND`/`METHOD_NOT_ALLOWED`/...) and a catch-all `Exception` → 500 `INTERNAL_ERROR` that does not echo request data.

### M6 — `/docs` will not show the real error responses (Rubric, FR-15)
- **Location:** API Endpoints `/docs`, AD-8.
- **Issue:** FastAPI documents only its default `HTTPValidationError` 422 schema, which is not the custom shape. It documents no 404/503 unless the routes declare them. FR-15 requires the docs to cover error responses.
- **Fix:** Define `ErrorResponse` in `api/schemas.py`. Every route declares `responses=COMMON_ERRORS` (a shared dict in `api/errors.py`) with the correct 404/422/503 entries.

### M7 — Seed dates absolute vs clock-relative (Adversary: seed story vs date-boundary tests)
- **Location:** AD-2, AD-6, AD-10 (seed).
- **Issue:** If the seed uses absolute delivery dates, the "inside the Return Window" order from FR-15 expires 30 days after the dates were written, which breaks local and Docker demos and UJ-1. If the seed is relative to the real date, a test story that hard-codes a fixed clock date disagrees with it. Both choices obey every AD.
- **Fix:** `seed.py` computes dates as offsets from `clock.today()`, which `create_app` passes in (e.g. inside window = today−12, expired = today−31). Document the offsets in `seed.py`. Tests pass a fixed clock, so the result is deterministic either way.

### M8 — `pydantic-settings` used but not in the Stack table (Currency, NFR-3)
- **Location:** Conventions "Config", Stack.
- **Issue:** `pydantic-settings` is a separate package (it has not been part of `pydantic` since v2). It is not pinned in the Stack table, so stories may add it ad hoc or skip it. It also adds little when every value is a default.
- **Fix:** Either add `pydantic-settings` with a version checked on PyPI to the Stack table, or drop it and use a frozen dataclass/Pydantic model of constants in `core/settings.py`.

## Low (12)

| # | Location | Issue | Fix |
| --- | --- | --- | --- |
| L1 | AD-1, AD-6 | Import-direction and no-`datetime.now` rules are written down but nothing enforces them mechanically. | Add `import-linter` layer contracts and a ruff `TID251` banned-API rule for `datetime.now`/`utcnow`/`date.today` to CI. |
| L2 | Deployment (CI) | `bandit -r src` exits non-zero on *any* severity and `pip-audit` audits whatever environment it runs in, not necessarily the locked one. | `bandit -r src --severity-level high`; `uv export --frozen --no-hashes \| uv run pip-audit -r /dev/stdin` (or `uv run pip-audit`). Pin both in dev deps. |
| L3 | Stack `uv 0.12.x`, Dockerfile | The uv version is unpinned and was not checked today. `python:3.12-slim` does not ship uv. | Pin the exact uv version (setup-uv in CI, `COPY --from=ghcr.io/astral-sh/uv:<ver>` in Docker). Run as a non-root user. |
| L4 | Deployment (CI), NFR-3 | No secrets scan, although the addendum suggests gitleaks and CLAUDE.md forbids committing `.env`. | Add a gitleaks step (or pre-commit) to CI. |
| L5 | AD-1, AD-8, FR-14 | The health check's owner and the exception that produces 503 `UNHEALTHY` are unspecified. A router running `SELECT 1` through `core` sidesteps AD-1's intent. | Add `HealthService.check()` raising `ServiceUnavailableError` (in `domain/errors.py`), mapped in `api/errors.py`. |
| L6 | AD-7 | Whether emails are `EmailStr` or `str` is undefined. `EmailStr` needs `email-validator`, which is not in the Stack table, and would make POST reject inputs the GET header accepts. | State: plain non-empty `str`, normalized `strip().lower()`, no format validation. |
| L7 | AD-7, AD-8 | The `RequestValidationError` handler may put Pydantic's `input` (which can be the email) into `message`. | The handler builds `message` from `loc` and `type` only, never from `input`. |
| L8 | Structural Seed | The ERD shows `ORDER_LINES ||--o{ RETURN_LINES`, but `return_lines` has no `order_id`, so only the `sku → products` FK exists. | Fix the ERD or add `order_id` to `return_lines` with a composite FK to `order_lines`. |
| L9 | Deployment, NFR-5 | "Merging requires all to pass" depends on branch protection, which the spine does not mention. | Note the required status checks on `main`. |
| L10 | API `GET /audit-events`, FR-1 | An unfiltered audit list reveals every real Order ID, which defeats FR-1's anti-enumeration goal. The PRD accepts this (Q1), but the spine does not say so. | Add a line under Deferred / Auth noting this accepted risk. |
| L11 | AD-5 | Converting cents to `Decimal` (`Decimal(4000)/100` gives `40`, not `40.00`) has no single helper, so JSON could show `"40"`. | Add one `cents_to_decimal`/`decimal_to_cents` helper (quantize to `0.01`) in `domain/money.py`. Repositories call it. |
| L12 | AD-2, Structural Seed | `schema.sql` has no named owner story, and `PRAGMA foreign_keys` (off by default in SQLite) is unstated. | The foundation story creates the full schema. State `PRAGMA foreign_keys = ON`. |

## Currency notes (verified / not flagged)

- Stack versions match the PyPI check given (fastapi 0.162.2, pydantic 2.14.3, uvicorn 0.54.0, pytest 9.2.0, pytest-cov 7.1.0, httpx 0.28.1, pip-audit 2.10.1, bandit 1.9.4).
- `fastapi.testclient` needs `httpx`, which is correctly listed.
- Pydantic v2 serializes `Decimal` as a JSON string and UTC datetimes with `Z`, which is consistent with AD-5 and the Conventions, provided values are quantized (L11).
- `:memory:` with `check_same_thread=False` and one worker is workable only with full serialization (M1).
- Opening the DB in `create_app` rather than in lifespan correctly avoids TestClient lifespan pitfalls.
