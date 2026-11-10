---
title: Retail Returns Assistant
status: final
created: 2026-11-10
updated: 2026-11-10
---

# PRD: Retail Returns Assistant

## 0. Document Purpose

This PRD defines v1 of the Retail Returns Assistant, an internal training project. It is the input for `docs/architecture.md` and for the stories in `docs/stories/`. Its only source is the product brief (`docs/brief.md`). Domain terms are defined once in §3 Glossary and used exactly as written there. Features in §4 contain globally numbered requirements (FR-1…FR-15). Anything inferred rather than confirmed is tagged `[ASSUMPTION]` inline and listed again in §11. Technology and tooling detail that belongs downstream is kept in `addendum.md`.

## 1. Vision

Customers contact support just to find out where an order is or to start a return. The Retail Returns Assistant is a self-service REST API that handles both jobs without a person involved. A customer looks up an order. If the order is inside the return window, the customer requests a return, and the system works out the refund and puts the items back into inventory in the same step.

Every action the system takes is written to an audit trail. When a customer disputes an outcome, support staff can see exactly what happened and why, without asking an engineer.

This is a training project. All data is mock data and nothing touches real payments or a warehouse. The product goal is a small, correct, well-tested API. The project goal is to practise the full BMAD loop on it: PRD, architecture, stories, QA gate, CI.

## 2. Target Users

### 2.1 Jobs To Be Done

- **Customer:** "Tell me the status of my order without waiting for support."
- **Customer:** "Let me return something I don't want, and tell me straight away how much I'll get back."
- **Support Staff:** "When a customer questions a return or refund, show me the full history of that order so I can answer in one look."

### 2.2 Non-Users (v1)

- Warehouse, finance and logistics staff. No real fulfilment, payment or shipping systems are connected.
- Administrators managing products, orders or prices. All data is seeded mock data.

### 2.3 Key User Journeys

- **UJ-1. Asha returns one of two items from a delivered order.** Asha bought a jacket and a scarf, and the order arrived 12 days ago. She looks up the order with her order ID and email and sees it is `delivered`, with a return deadline 18 days away. She requests a return of the scarf. The response confirms the return, shows a refund of the scarf's price, and the scarf is back in inventory. **Edge case:** on day 31 the same request is denied with reason `RETURN_WINDOW_EXPIRED`, and the denial is recorded in the audit trail.
- **UJ-2. Ravi from support explains a denied return.** A customer says the system "refused" their return. Ravi reads the audit trail filtered by the order ID. He sees the lookup, the denied return request with reason `ITEM_NOT_RETURNABLE`, and its timestamp, and he explains the outcome to the customer.

## 3. Glossary

- **Customer** — The person who placed an Order. Identified only by the email address on the Order. There are no accounts.
- **Support Staff** — Internal staff who read the Audit Trail. They have no write actions.
- **Order** — A purchase made by one Customer. It has an Order ID, an Order Status, one or more Line Items and, once delivered, a Delivery Date.
- **Order Status** — One of `placed`, `shipped`, `delivered`, `cancelled`. `[ASSUMPTION]` These four values are enough for v1.
- **Line Item** — One Product on an Order, with the quantity purchased and the unit price paid.
- **Product** — A sellable item identified by a SKU. It carries a `returnable` flag and an Inventory level.
- **Inventory** — The on-hand quantity of a Product (mock).
- **Delivery Date** — The calendar date (UTC) on which an Order became `delivered`.
- **Return Window** — The 30 calendar days after the Delivery Date. Day 30 is included.
- **Return** — An accepted request to send back one or more Return Lines from a single Order. An Order can have several Returns.
- **Return Line** — One Line Item and the quantity being returned within a Return.
- **Denial Reason** — A machine-readable code explaining why a return request was rejected (see FR-5).
- **Refund** — The amount owed to the Customer for a Return, as calculated by FR-8. It is recorded only; no money moves.
- **Restock** — Adding a Return Line's quantity back to its Product's Inventory.
- **Audit Event** — One immutable record of an action the system took or refused.
- **Audit Trail** — All Audit Events, in time order.

## 4. Features

### 4.1 Order Lookup

**Description:** A Customer gives an Order ID and the email on the Order and gets back the Order's current state. The response includes the Line Items, how much of each has already been returned, and whether a return is still possible and until when. Realizes UJ-1.

#### FR-1: Look up an Order

A Customer can retrieve an Order by Order ID plus email. `[ASSUMPTION]` Requiring the email as well as the ID stands in for authentication; the brief's "no login" rules out anything stronger.

**Consequences (testable):**
- A matching Order ID and email (email compared case-insensitively) returns the Order ID, Order Status, order date, Delivery Date (or null), and each Line Item's SKU, name, quantity purchased, quantity already returned and unit price.
- The response includes `return_eligible_until`, which is the Delivery Date + 30 days, or null if the Order is not `delivered`.
- The response lists the Order's existing Returns: their IDs, Refund amounts and creation times.
- An unknown Order ID and a known Order ID with the wrong email return the **same** not-found response, so the endpoint cannot be used to discover which Order IDs exist.

#### FR-2: Audit every lookup

Every lookup attempt, successful or not, creates an Audit Event (see FR-11).

### 4.2 Return Request

**Description:** A Customer asks to return specific quantities of specific Line Items from one Order. The system either accepts the whole request or rejects it with a Denial Reason. Partial acceptance is not possible. If the request is accepted, the Refund is calculated and the items are Restocked in the same operation. Realizes UJ-1 and UJ-2.

#### FR-3: Request a Return

A Customer can submit a return request containing the Order ID, the email and one or more Return Lines (SKU + quantity). `[ASSUMPTION]` Returns are made per Line Item and quantity, not per whole Order.

**Consequences (testable):**
- If every rule in FR-4 passes, a Return is created and the response contains the Return ID, the Return Lines, the Refund amount and the creation timestamp.
- If any rule fails, no Return is created, no Inventory changes, and the response contains the Denial Reason for the first rule that failed.

#### FR-4: Eligibility rules

A return request is accepted only if all of the following are true:
1. The Order exists and the email matches it. Otherwise the result is the same not-found response as FR-1.
2. The Order Status is `delivered`.
3. The request date (UTC) is no later than Delivery Date + 30 days. `[ASSUMPTION]` Day 30 is included and dates are calendar days in UTC.
4. Each SKU in the request appears on the Order, and no SKU appears twice in the same request.
5. Each Product is `returnable`.
6. Each requested quantity is ≥ 1 and ≤ (quantity purchased − quantity already returned).

**Consequences (testable):**
- A request on day 30 after delivery is accepted. A request on day 31 is denied.
- The boundary in rule 3 can be tested deterministically, without depending on the real wall clock.

#### FR-5: Denial Reasons

Each failed rule maps to a stable Denial Reason code: `ORDER_NOT_DELIVERED`, `RETURN_WINDOW_EXPIRED`, `ITEM_NOT_ON_ORDER`, `ITEM_NOT_RETURNABLE`, `QUANTITY_EXCEEDS_RETURNABLE`, `INVALID_REQUEST` (for no lines, a duplicate SKU, or a quantity below 1). Request-shape errors such as missing fields or wrong types are rejected before the business rules run.

#### FR-6: Multiple Returns per Order

An Order can have more than one Return until every Line Item has been fully returned. `[ASSUMPTION]`

**Consequences (testable):**
- After returning 1 of 2 units, a second request for 1 unit succeeds and a third request for 1 unit is denied with `QUANTITY_EXCEEDS_RETURNABLE`.

#### FR-7: View a Return

A Customer can retrieve one Return by Return ID plus the Order's email. The response contains its Return Lines, Refund and creation time. An unknown Return ID and a wrong email return the same not-found response.

### 4.3 Refund Calculation

**Description:** Each Return has a Refund amount, calculated when the Return is accepted. No payment is made. The amount is stored with the Return.

#### FR-8: Calculate the Refund

Refund = sum over Return Lines of (unit price paid × quantity returned). `[ASSUMPTION]` Shipping is not refunded, there is no restocking fee, and every Order uses one currency.

**Consequences (testable):**
- Amounts are exact decimal values to 2 places, rounded half-up. Floating-point arithmetic is never used for money.
- For a Line Item bought at 19.99 × 3, returning 2 units gives a Refund of 39.98.
- The Refund is stored with the Return and never recalculated afterwards.

### 4.4 Restock Inventory

**Description:** Accepting a Return puts its items back into stock immediately. There is no inspection or warehouse receiving step in v1. `[ASSUMPTION]`

#### FR-9: Restock on accepted Return

When a Return is accepted, each Return Line's quantity is added to its Product's Inventory.

**Consequences (testable):**
- The Return, the Refund and every Restock either all happen or none happen. If any part fails, nothing changes.
- Two return requests that both try to claim the last returnable unit never both succeed.

#### FR-10: View Inventory

Anyone can read a Product's current Inventory by SKU, so the effect of a Restock can be seen through the API. `[ASSUMPTION]` This endpoint was added for observability. It is not listed in the brief.

### 4.5 Audit Trail

**Description:** Every customer-facing action produces an Audit Event, whatever its outcome. Support Staff read the Audit Trail to answer disputes. Realizes UJ-2.

#### FR-11: Record Audit Events

The system records an Audit Event for each of:
- an order lookup (outcome `found` or `not_found`)
- a return request (`accepted` or `denied` + Denial Reason)
- the Refund calculated for an accepted Return
- each Restock (SKU + quantity)
- a Return view

**Consequences (testable):**
- Each Audit Event has an event ID, a UTC timestamp, an action type, an outcome, the Order ID (if one was supplied), the Return ID (if one exists) and a details object.
- `[ASSUMPTION]` Audit Events never contain the Customer's email or any other personal data beyond the Order ID.
- An accepted Return produces its Audit Events in the same all-or-nothing operation as FR-9.

#### FR-12: Read the Audit Trail

Support Staff can list Audit Events, filtered by Order ID, action type and time range. Results are newest first and paginated. `[ASSUMPTION]` There is no access control, since the brief has no login. See §10 Q1.

#### FR-13: Audit Trail is append-only

There is no API to change or delete an Audit Event.

### 4.6 Service Operations

#### FR-14: Health check

`GET /healthz` returns HTTP 200 with `{"status": "ok"}` when the service can read its data store. Otherwise it returns 503.

#### FR-15: API documentation and mock data

- Interactive API documentation is served at `/docs`. It covers every endpoint, with request and response schemas and the error responses.
- On startup the service loads a fixed, documented set of seed data, in memory, that covers at least: an Order inside the Return Window, an Order outside it, an Order not yet delivered, a `cancelled` Order, a non-returnable Product, and an Order that has already been partly returned. Restarting the service resets all data, including Returns and Audit Events.

## 5. Cross-Cutting Non-Functional Requirements

- **NFR-1 Error contract.** All errors use one JSON shape: `{"error": {"code", "message"}}`. HTTP statuses: 404 not found, 422 for request-shape errors and denied return requests, 503 unhealthy. `[ASSUMPTION]` Denials use 422, not 409.
- **NFR-2 Testing.** Every FR has automated tests. Business logic (eligibility, Refund, Restock, audit) has ≥ 90% line coverage, enforced in CI.
- **NFR-3 Security hygiene.** No secrets are committed. Dependencies are pinned. Dependency and static-analysis scans report zero high or critical findings, as a CI gate.
- **NFR-4 Portability.** The service runs the same way locally and in a Docker container.
- **NFR-5 CI.** Every pull request runs tests, the coverage gate and the security scans on GitHub Actions, and merging requires all of them to pass.
- **NFR-6 Determinism.** Seed data and "today" can be controlled in tests, so date-boundary tests give the same result on every run.
- **NFR-7 Performance.** There is deliberately no performance target in v1.

## 6. Constraints

These come from the brief and are fixed: Python 3.12, FastAPI, Pydantic, SQLite (in-memory mock data), pytest with pytest-cov, Docker, GitHub Actions. Tool-level choices (scanners, Docker base image, clock injection) are in `addendum.md` for the architecture.

## 7. Non-Goals

- Authentication, authorization or customer accounts.
- Real payments, payment gateways or refund payouts.
- Shipping labels, carriers, returns logistics, or warehouse receiving and inspection.
- Any UI: no web or mobile front end, no admin console.
- A conversational, chat or LLM "agent" layer. v1 is strictly REST.
- Exchanges, store credit, partial refunds for damaged items, restocking fees.
- Notifications (email/SMS).
- Data persistence across restarts.

## 8. MVP Scope

### 8.1 In Scope

Order lookup (FR-1–2), return requests with eligibility rules and Denial Reasons (FR-3–7), Refund calculation (FR-8), Restock and an inventory view (FR-9–10), the Audit Trail (FR-11–13), `/healthz`, `/docs` and seed data (FR-14–15), and NFR-1–6.

### 8.2 Out of Scope for MVP

Everything in §7. Cancelling a Return and a return approval step for Support Staff are deferred to v2 if the project continues.

## 9. Success Metrics

**Primary**
- **SM-1:** Every FR has at least one passing automated test that checks its stated consequences. Validates FR-1–FR-15.
- **SM-2:** Business-logic line coverage ≥ 90%, gated in CI. Validates NFR-2.

**Secondary**
- **SM-3:** Dependency and static-analysis scans report zero high or critical findings on `main`. Validates NFR-3.
- **SM-4:** `docker run` of the built image answers `GET /healthz` with 200, and `/docs` loads. Validates FR-14, FR-15, NFR-4.
- **SM-5:** Every story has a QA gate in `docs/qa/gates/` marked PASS before it is merged. Validates NFR-5.

**Counter-metrics (do not optimize)**
- **SM-C1:** Raw coverage percentage. Tests that run code without checking FR consequences inflate it. Counterbalances SM-2. Reviewers check assertions, not just the number.
- **SM-C2:** Number of endpoints or features shipped. Adding scope beyond §8.1 is not a win. Counterbalances SM-1.

## 10. Open Questions

1. **Audit access.** The Audit Trail is readable by anyone who can reach the API. That is acceptable for a local training project, but would it need restricting if the service were ever deployed beyond localhost? *Owner: PM. Revisit: before any shared deployment.*
2. **Return cancellation.** Should a Customer be able to cancel a Return, which would reverse the Restock and void the Refund? *Owner: PM. Revisit: if a v2 is planned.*

## 11. Assumptions Index

- §3 — Order Status has four values: `placed`, `shipped`, `delivered`, `cancelled`.
- FR-1 — Order ID + email is the only identity check. A mismatch looks the same as an unknown Order.
- FR-3 — Returns are per Line Item and quantity.
- FR-4 — The Return Window counts calendar days in UTC, and day 30 is included.
- FR-6 — An Order can have several Returns.
- FR-8 — No shipping refund, no restocking fee, one currency, 2-decimal half-up rounding.
- §4.4 — Restock happens as soon as the Return is accepted, with no inspection step.
- FR-10 — There is a read-only inventory endpoint (not in the brief).
- FR-11 — Audit Events contain no Customer email or other personal data.
- FR-12 — The Audit Trail has no access control.
- NFR-1 — Denied return requests return HTTP 422.
