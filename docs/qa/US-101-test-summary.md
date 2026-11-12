# Test Automation Summary — US-101

Date: 2026-11-10 · Scope: `GET /orders/{order_id}` (AC-1..AC-5) plus edge cases

## Generated Tests

### API Tests
- [x] `tests/api/test_orders_edge_cases.py` — 38 tests (new)
  - Malformed IDs (non-numeric, negative, zero, unprefixed numeric, fractional): uniform 404 `NOT_FOUND`, byte-identical to an unknown-ID 404
  - Malformed IDs write exactly one `ORDER_LOOKUP` / `not_found` audit row with the ID stored verbatim and a valid `occurred_at`
  - 404 audit rows (unknown ID, wrong email, near-miss email, another customer's order) contain no email
  - 404 audit row is committed before the error response (seq ordering across requests)
  - Email normalization variants (case, leading/trailing whitespace, tab)
  - Line shape and 2dp `unit_price` string format; delivered-but-expired order still reports its deadline
  - Missing or misnamed `X-Customer-Email` header gives 422 `INVALID_REQUEST`, whatever the ID; no audit row; no value echoed

### Existing (unchanged)
- `tests/api/test_orders.py` — AC-1..AC-5 happy paths, AC-3 identical 404s, AC-5 audit rows, 500 handler

## AC Traceability

| AC | Tests |
|----|-------|
| AC-1 | `test_orders.py::test_successful_lookup`, edge: email variants, line shape |
| AC-2 | `test_orders.py::test_shipped_order_has_null_dates`, `test_cancelled_order_has_null_dates`, edge: old delivered order |
| AC-3 | `test_orders.py::test_unknown_id_and_wrong_email_are_identical_404s`, edge: malformed IDs |
| AC-4 | `test_orders.py::test_missing_or_blank_email_header_is_422`, edge: header vs ID, misnamed header, no echo |
| AC-5 | `test_orders.py::test_each_lookup_writes_exactly_one_audit_event`, edge: malformed-ID and 404 audit rows |

## Results
- `uv run pytest`: **211 passed**, 0 failed (173 existing + 38 new)
- Coverage of `domain/` + `services/`: **100%** (gate is 90%)
- Test bugs fixed: none needed. Product code: unchanged.

## Next Steps
- Run in CI
- Revisit when US-102 adds `returns` (`quantity_returned` > 0)
