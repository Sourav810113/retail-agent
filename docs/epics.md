---
status: final
stepsCompleted: [step-01-validate-prerequisites, step-02-design-epics, step-03-create-stories, step-04-final-validation]
inputDocuments: [docs/prd.md, docs/architecture.md]
---

# Retail Returns Assistant — Epic Breakdown

There is a single epic, **Epic 1: Self-service returns API**. It is delivered as four prioritized stories, each in its own file in `docs/stories/`.

| Priority | Story | Summary | Depends on |
| --- | --- | --- | --- |
| 1 | [US-101](stories/US-101.md) | Project skeleton, order lookup, `/healthz`, lookup audit, seed data | — |
| 2 | [US-102](stories/US-102.md) | Return request, eligibility rules, Denial Reasons, Refund | US-101 |
| 3 | [US-103](stories/US-103.md) | Restock, inventory view, view a Return | US-101, US-102 |
| 4 | [US-104](stories/US-104.md) | Audit Trail API, Docker, CI + security scans | US-101–US-103 |

## FR / NFR coverage map

| Requirement | Story |
| --- | --- |
| FR-1 | US-101 (lookup), US-102 (`returns[]`, `quantity_returned`) |
| FR-2 | US-101 |
| FR-3, FR-4, FR-5, FR-6, FR-8 | US-102 |
| FR-7, FR-9, FR-10 | US-103 |
| FR-11 | US-101 (lookup), US-102 (return/refund), US-103 (restock/view) |
| FR-12, FR-13 | US-104 |
| FR-14 | US-101 |
| FR-15 | US-101 (seed, `/docs`), US-104 (`/docs` completeness) |
| NFR-1, NFR-6 | US-101 (established), US-102 |
| NFR-2 | every story (coverage gate set up in US-101) |
| NFR-3, NFR-4, NFR-5 | US-104 |
| NFR-7 | n/a (no performance target) |

Every table is created by the first story that needs it:
- `products`, `orders`, `order_lines`, `audit_events` in US-101
- `returns`, `return_lines` in US-102

No story depends on a later story.
