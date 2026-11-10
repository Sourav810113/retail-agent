# Retail Agent — project memory

## Method
- Use BMAD: read docs/prd.md, docs/architecture.md, and the active story in docs/stories/
- Save BMAD planning documents in docs/ (not _bmad-output/)
- One branch and one commit per story: feat(us-<id>): ...
- QA gate in docs/qa/gates/ must PASS before merge

## Stack
- Python 3.12, FastAPI, Pydantic, SQLite (mock in-memory data)
- pytest + pytest-cov; new behaviour requires tests; >= 90% coverage on business logic
- Run: uvicorn src.retail_agent.main:app --port 8000

## Rules
- Never commit secrets (.env); never read .env files
