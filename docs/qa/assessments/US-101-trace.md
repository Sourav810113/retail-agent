# US-101 — Requirements Traceability (AC-1..AC-4)

- Story: `docs/stories/US-101.md`
- Run: `uv run pytest -q --cov=src` on 2026-11-10, branch `feature/us-101-returns` (uncommitted working tree)
- Result: **229 passed, 0 failed, 0 errors, 0 skipped**; coverage of `src/` **99.40%** (501 statements, 3 missed: `api/errors.py` 52, 113-114)
- Per-test status comes from the run's JUnit XML. `n/n` counts parametrized cases.

| AC | Requirement | Proving tests | Cases | Status |
|----|-------------|---------------|-------|--------|
| AC-1 | `GET /orders/ORD-1001` with `Asha@Example.com ` returns 200 with `order_id`, `status`, `order_date`, `delivery_date` and `lines[]` (`sku`, `name`, `quantity`, 2dp `unit_price`, `quantity_returned`); `return_eligible_until` = D + 30; email absent from the response | `tests/api/test_orders.py::test_successful_lookup` (full body equality; email absent from body and headers) | 1/1 | PASS |
| | | `tests/api/test_orders_edge_cases.py::test_email_is_matched_case_and_whitespace_insensitively` | 5/5 | PASS |
| | | `tests/api/test_orders_edge_cases.py::test_line_shape_and_money_format` | 1/1 | PASS |
| | | `tests/unit/test_services.py::test_lookup_found` | 1/1 | PASS |
| | | `tests/unit/test_domain.py::test_normalize_email`, `::test_email_matches_is_case_and_whitespace_insensitive` | 5/5 | PASS |
| | | `tests/unit/test_domain.py::test_return_eligible_until_is_delivery_plus_30` | 1/1 | PASS |
| AC-2 | A `shipped` Order returns 200 with `delivery_date: null`, `return_eligible_until: null` | `tests/api/test_orders.py::test_shipped_order_has_null_dates` | 1/1 | PASS |
| | | `tests/api/test_orders.py::test_cancelled_order_has_null_dates` | 1/1 | PASS |
| | | `tests/unit/test_domain.py::test_return_eligible_until_null_when_not_delivered` | 3/3 | PASS |
| AC-3 | Unknown ID and known ID + wrong email both return 404 with the identical body `{"error": {"code": "NOT_FOUND", "message": "Order not found"}}` | `tests/api/test_orders.py::test_unknown_id_and_wrong_email_are_identical_404s` (JSON and byte equality) | 1/1 | PASS |
| | | `tests/unit/test_services.py::test_lookup_unknown_and_wrong_email_raise_identical_errors` | 1/1 | PASS |
| | | `tests/api/test_orders_edge_cases.py::test_malformed_id_returns_uniform_404`, `::test_malformed_id_404_is_byte_identical_to_unknown_id_404` (non-numeric, negative, zero, unprefixed, fractional) | 14/14 | PASS |
| | | `tests/api/test_orders_edge_cases.py::test_over_long_id_is_uniform_404_audited_truncated`, `::test_over_long_id_with_real_prefix_does_not_match` | 3/3 | PASS |
| AC-4 | No `X-Customer-Email` header returns 422 `{"error": {"code": "INVALID_REQUEST", ...}}` | `tests/api/test_orders.py::test_missing_or_blank_email_header_is_422` (missing, empty, blank; no audit row) | 3/3 | PASS |
| | | `tests/api/test_orders_edge_cases.py::test_missing_header_is_422_regardless_of_id` | 3/3 | PASS |
| | | `tests/api/test_orders_edge_cases.py::test_misnamed_email_header_is_422` | 1/1 | PASS |

**Summary:** 4/4 acceptance criteria traced; 4/4 PASS.

## Known weaknesses in the tracing tests

These do not change any status above. They are listed as open findings in `docs/stories/US-101.md` → Review Findings.

- `test_422_message_does_not_echo_header_value` (AC-4 extra) checks only the response keys, not the message text, so it cannot detect an echo. AC-4's own requirement is fully covered by the tests in the table.
- `test_old_delivered_order_still_reports_deadline` (AC-2 extra) only asserts that the value is not null. It is not used as evidence in the table.
- IDs containing `/` or `%2F`, and an empty ID, get the router's 404 (`"Not found"`) rather than the AC-3 body. The review accepted this, because such requests never reach the lookup endpoint, but no test pins it yet.

## Out of scope for this trace

AC-5 to AC-8 (audit, health, framework errors, seed/docs, quality rules) are also covered and green in the same run. Examples: `test_each_lookup_writes_exactly_one_audit_event`, `tests/api/test_health_and_errors.py`, `tests/api/test_seed_and_docs.py`, `tests/test_architecture.py`. This document does not trace them.
