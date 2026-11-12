# Reconciliation — docs/brief.md vs PRD
| Brief item | PRD |
|---|---|
| Look up order + status | FR-1 |
| Return within 30-day delivery window | FR-3, FR-4 |
| Compute refund | FR-8 |
| Restock inventory | FR-9 |
| Every action logged to audit trail | FR-2, FR-11–13 |
| Mock data only (SQLite) | FR-15, §6, §7 |
| REST + /docs + /healthz | FR-14, FR-15 |
| pytest, >= 90% business-logic coverage | NFR-2, SM-2 |
| No secrets; deps scanned & pinned | NFR-3, SM-3 |
| Local AND Docker; CI on GitHub Actions | NFR-4, NFR-5, SM-4 |
Gaps: none. Additions beyond brief: FR-7, FR-10 (tagged).
