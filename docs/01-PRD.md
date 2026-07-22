# PRD — Loan Disbursement Orchestration Platform

## 1. Problem statement

The bank originates personal loans through three channels — a self-serve portal,
broker referrals over email, and batch feeds from financial aggregators. The target
is funding within 48 hours of submission; today it averages **four days**. The gap
isn't any single slow step — it's that the process is manual and stateful work
(tracking where an application is, chasing missing documents, re-triggering stalled
third-party checks, remembering to resume after a human decision) is being done by
people instead of a system built for exactly that job.

Three consequences fall out of that:

- **Applications stall silently.** Nobody is watching a clock per application, so
  delay is discovered late, not prevented early.
- **Processors lack visibility.** "Where is application #4821 right now, and why?"
  is a manual lookup, not a query.
- **Applicants abandon.** Every extra day of ambiguity is a day the applicant can
  walk to a competitor or a different product entirely.

## 2. Goals

| Goal | Metric | Target |
|---|---|---|
| Faster funding | Median time from submission → funded | ≤ 48 hours |
| Fewer stalls | % of applications with no state change for > 24h while non-terminal | < 5% |
| Full visibility | % of applications with real-time, queryable status | 100% |
| Regulatory readiness | % of decisions (automated or human) with a complete audit trail | 100% |
| Scale headroom | Sustained monthly volume without redesign | 50,000 applications/mo |
| Reduced abandonment | Applicant drop-off rate during processing | Directionally down (not directly measurable in this exercise — instrumented, not proven) |

## 3. Non-goals (explicitly out of scope for this exercise)

- Real integrations with an actual credit bureau, KYC/identity provider, fraud
  vendor, or core banking disbursement system. These are **mocked** behind stable
  interfaces so the orchestration logic is real even though the vendors aren't.
- Production-grade authentication/authorization on the ops dashboard (a real
  deployment needs SSO + RBAC for loan officers vs. compliance vs. admins).
- OCR / automated document content verification — documents are tracked as
  present/missing/verified, not parsed.
- A fully generalized rules engine / DSL for underwriting — product logic is
  isolated cleanly (see §7 of the system design doc) but implemented in code, not
  a no-code rules authoring tool. Flagged as future work.

See [05 — Trade-offs & Future Work](./05-tradeoffs-and-future-work.md) for the full
list and reasoning.

## 4. Users / personas

| Persona | Needs |
|---|---|
| **Applicant** (via portal) | Submit an application, know what's missing, know the outcome |
| **Broker** (via email) | Submit a client's application without adopting the bank's tooling |
| **Aggregator / partner system** (via batch feed) | Push many applications at once, get back per-record success/failure |
| **Loan Ops / Underwriter** | See what needs a decision, make it, trust that the system resumes correctly |
| **Compliance / Audit** | Reconstruct exactly what happened and why, for any application, at any time |
| **Engineering / Platform** | Add a new loan product or a new third-party provider without destabilizing existing ones |

## 5. Functional requirements

1. Ingest applications from all three channels into one canonical representation.
2. Validate completeness (required documents/fields) per loan product.
3. Enrich with third-party checks: credit, identity, fraud.
4. Underwrite automatically where policy allows; otherwise route to a human.
5. Let a human reviewer approve, decline, or escalate — and have the system resume
   exactly where it left off.
6. Disburse funds exactly once on approval.
7. Reach a terminal state for every application: **funded**, **declined**, or
   **escalated** (handed to a manual/off-platform process).
8. Give operators a live view of every application's status and history.
9. Record every automated and human decision in a form compliance can query.

## 6. Non-functional requirements

- **Scale:** 8,000/mo today → 50,000/mo (~1,700/day at peak), across three very
  different ingestion shapes (interactive, semi-structured email, large batch).
- **Resilience:** third-party providers have rate limits, partial failures, and
  outages. The system must degrade gracefully — retry, back off, isolate one
  provider's failure from another's — without losing an application's progress.
- **Auditability:** every decision (automated or human) must be reconstructable:
  what happened, when, by whom/what, and why.
- **Product isolation:** personal, auto, and debt-consolidation loans have distinct
  underwriting rules, document requirements, and risk thresholds. One product's
  logic must not leak into another's, and adding a fourth product shouldn't require
  touching the first three.
- **SLA-awareness:** the system should know when an application is at risk of
  missing the 48-hour target *before* it misses it, not after.
- **Operability:** when something breaks, an operator or engineer needs to be able
  to find out what, why, and what's affected — quickly.

## 7. Success metrics (how we'd know this worked)

- p50 / p95 time-to-funded, by channel and by product.
- Count and duration of applications sitting in `AWAITING_DOCUMENTS` or
  `NEEDS_HUMAN_REVIEW`.
- Third-party failure/retry rate, by provider.
- % of applications requiring human review, by product (a proxy for how well
  automated underwriting policy is tuned).
- Zero double-disbursements, zero un-auditable terminal states.

## 8. Assumptions

- Third-party providers expose synchronous request/response APIs with per-provider
  rate limits (stated in the case study); none are assumed to support webhooks for
  this exercise, though that's noted as a future optimization.
- The core banking disbursement API supports an idempotency key — this is treated
  as a hard requirement to negotiate with that team in a real build, since
  exactly-once funding isn't safely achievable without it.
- "Escalated" is a legitimate terminal state, distinct from the transient
  "waiting for a human reviewer" state inside the normal flow. See the state
  machine in the system design doc for the distinction.
