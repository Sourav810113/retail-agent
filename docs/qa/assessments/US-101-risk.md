# US-101 — Risk Assessment

- Story: `docs/stories/US-101.md` (order lookup, health check, lookup audit)
- Assessed: 2026-11-10, against the working tree after the code-review fixes
- Evidence run: `uv run pytest -q --cov=src` gave 229 passed / 0 failed, with 99.40% coverage of `src/`
- Scale: likelihood and impact are each **low / med / high**. Status is **mitigated** (tests prove the control), **partial** (control exists, with a known residual), or **open** (no control yet).

| ID | Risk | Likelihood | Impact | Status | How tests cover it |
|----|------|-----------|--------|--------|--------------------|
| R1 | **Order enumeration**: a caller can tell "unknown order" from "wrong email" (AC-3) | med | high | mitigated | `test_unknown_id_and_wrong_email_are_identical_404s` compares bodies byte for byte. Malformed and over-long IDs are proven byte-identical to an unknown ID (`test_malformed_id_404_is_byte_identical_to_unknown_id_404`, `test_over_long_id_is_uniform_404_audited_truncated`). The service raises the same error for both cases. |
| R2 | **Customer email leaks** into the response, headers, audit rows or logs (AD-7) | med | high | mitigated | Response and headers: `test_successful_lookup`, `test_unknown_id_and_wrong_email_are_identical_404s`. Audit: `test_each_lookup_writes_exactly_one_audit_event` and `test_404_writes_exactly_one_audit_event_without_email` (no `@` in any column). Logs: since the review fix, the 500 path no longer re-raises to uvicorn (`test_unexpected_exception_is_not_reraised_to_the_server`, `test_unexpected_exception_log_omits_request_data`), and this was re-checked against real uvicorn. |
| R3 | **Lookup not audited**, or the 404 audit row lost on the error path (AC-5) | med | high | mitigated | `test_each_lookup_writes_exactly_one_audit_event` (found and not_found), `test_malformed_id_writes_not_found_audit_event` (7 ID shapes), `test_lookup_not_found_is_audited_and_committed_before_raise`. A failure partway through rolls back the audit row (`test_lookup_unexpected_error_rolls_back_audit`). |
| R4 | **Audit storage exhaustion** from huge attacker-supplied order IDs in the in-memory DB | med | med | partial | Since the review fix, IDs over 64 characters skip the lookup and are audited cut to 64 (`test_over_long_id_is_uniform_404_audited_truncated`, `test_id_at_length_limit_is_audited_verbatim`, `test_lookup_over_long_id_skips_repository_and_truncates_audit`). Residual: nothing limits the request rate, so the audit log still grows by one row per request. |
| R5 | **Wrong return deadline** shown to the customer (D + 30, AC-1 / AC-2) | low | med | mitigated | `test_successful_lookup` asserts the exact date. `test_return_eligible_until_is_delivery_plus_30` and `test_return_eligible_until_null_when_not_delivered` cover the domain rule. Gap: no API test at a T−30 / T−31 boundary. Eligibility is US-102. |
| R6 | **Email normalization mismatch** rejects a real customer (case or whitespace) | med | med | mitigated | `test_email_is_matched_case_and_whitespace_insensitively` (5 variants), `test_normalize_email`, `test_email_matches_is_case_and_whitespace_insensitive`. |
| R7 | **Missing or blank email header** is accepted or crashes (AC-4) | low | med | mitigated | `test_missing_or_blank_email_header_is_422`, `test_missing_header_is_422_regardless_of_id`, `test_misnamed_email_header_is_422`. All check that no audit row is written. |
| R8 | **Money shown incorrectly** (float drift, wrong decimal places) | low | med | mitigated | `test_successful_lookup` (exact strings), `test_line_shape_and_money_format` (`\d+\.\d{2}`), and the unit tests in `tests/unit/test_money.py`. |
| R9 | **Route-level IDs** (`/`, `%2F`, empty) bypass lookup: router 404 body and no audit row | med | low | open | The review accepted this, because such requests never reach the lookup endpoint and reveal nothing about orders. No test pins the behaviour yet (open review item). |
| R10 | **Health check reports 500, not 503**, for errors that are not database errors (AC-6) | low | low | open | `test_health_fails_when_store_unreadable` covers only `sqlite3.Error`. A fix and test are still to come (open review item). |
| R11 | **Non-deterministic time**: wall-clock reads bypass the injected Clock (AC-8) | low | med | mitigated | `tests/test_architecture.py`. Since the review fix, the scanner also catches aliased imports, `datetime.today()`, `time.time()`/`time_ns()`, and bare references (`test_scanner_detects_wall_clock`, 12 cases). |
| R12 | **Vulnerable dependency or committed secret** | low | high | partial | Not covered by tests; covered by scans. On 2026-11-10 bandit (`-r src`) found 0 issues and pip-audit found 0 known vulnerabilities in 51 packages. gitleaks has **not run** (not installed), so the committed-secret part is unverified. |

## Residual risk summary

- No high-impact risk is open in the code. R1 to R3 are each mitigated by several tests.
- R12: the dependency and static scans are clean; the secret scan (gitleaks) is still pending.
- R9 and R10 are low-impact behaviours the review left open. R4 needs rate limiting, which is outside this story's scope.
