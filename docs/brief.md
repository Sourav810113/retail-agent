# Product Brief — Retail Returns Assistant

## Problem
Customers contact support just to check an order or start a return.
We want a self-service API that handles this automatically.

## Customer-visible behaviour
1. Customers can look up an order and its status
2. Customers can request a return within a 30-day delivery window
3. The system computes the refund and restocks inventory
4. Every action is logged to an audit trail
5. Mock data only (SQLite) — no real payments or warehouse

## Tech constraints
- Python 3.12, FastAPI, Pydantic, SQLite
- REST endpoints + /docs (Swagger) + /healthz
- pytest suite, >= 90% coverage on business logic
- No secrets in repo; dependencies scanned & pinned
- Runs locally AND in Docker; CI on GitHub Actions
