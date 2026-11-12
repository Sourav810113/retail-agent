# Addendum — Retail Returns Assistant PRD

Downstream detail that does not belong in the PRD itself. It is input for `docs/architecture.md`.

## Technology constraints (from brief)
- Python 3.12, FastAPI, Pydantic, SQLite in-memory with mock data; pytest + pytest-cov.
- Run locally with `uvicorn src.retail_agent.main:app --port 8000`, and in Docker.
- CI runs on GitHub Actions.

## Suggestions for architecture (not binding)
- **Clock injection.** A `today()` provider that can be replaced in tests, to satisfy NFR-6 and the FR-4 day-30/day-31 boundary tests.
- **Money.** Use `decimal.Decimal` throughout. Store amounts as integer cents or as TEXT decimals in SQLite (FR-8).
- **Atomicity.** Run the Return, Refund, Restock and Audit Event writes in one SQLite transaction (FR-9, FR-11). Re-check the returnable quantity inside that transaction.
- **Scanners.** Candidates for NFR-3: `pip-audit` (dependencies), `bandit` (SAST), `gitleaks` (secrets). Pin dependencies with a lock file.
- **Indicative endpoints:** `GET /orders/{order_id}?email=`, `POST /returns`, `GET /returns/{return_id}?email=`, `GET /inventory/{sku}`, `GET /audit-events`, `GET /healthz`, `GET /docs`.
- **Email in a query string.** It will show up in access logs. Consider a POST lookup or a header in the architecture.
