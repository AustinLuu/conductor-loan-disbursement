# Trade-offs, Retrospective & Future Work

This doc is the deliberate counterpart to [02 — System Design](./02-system-design.md):
that doc describes what's actually built; this one is what a more sophisticated
version would look like, and why it wasn't the right call for this exercise.

## Simplifications made for this build (and the upgrade path)

| Built this way | Would become this at real scale | Why the simple version is right here |
|---|---|---|
| One Temporal task queue for everything | Per-provider task queues (credit/identity/fraud/disbursement), each with `max_task_queue_activities_per_second` tuned to that provider's actual contract | Per-activity retry/backoff already handles rate limits and transient outages correctly at this volume and provider count. Queue-level isolation is a scaling knob for when one provider's outage is empirically starving the others — not a correctness requirement yet, and the activity boundary is already shaped to add it without a rewrite |
| SLA tracked via the `sla_deadline` column in Postgres + a dashboard filter | A scheduled `SLAMonitorWorkflow` (Temporal Schedule, e.g. every 15 min) proactively sweeping and paging ops before a breach | Reactive visibility — anyone can check current SLA status any time — satisfies "operators can see what's at risk." Proactive paging is an operational maturity add-on on top of that, not core functionality |
| Audit trail = one Postgres table, written by a separate activity alongside the state transition, not the same transaction | The audit write is part of the same transaction as the state change (or the workflow doesn't advance until an append-only sink acks) | Named here plainly rather than softened: this is closer to a gap against the audit requirement itself than a scale trade-off. Temporal's history isn't a permanent record (it ages out at the namespace retention horizon), so it can't backstop a dropped or delayed Postgres write — there's no reconciliation story today. One table is the right *shape* at this scale; the write not being transactional is the part I'd fix first, before anything else in this table |
| Batch fan-out via independent `start_workflow` calls in a tight loop | Same pattern, with backpressure so a 5,000-row file doesn't try to start 5,000 workflows at once | The dedup mechanism (deterministic workflow ID) is unchanged either way; throttling the fan-out itself is a small, isolated addition once real volume is known |
| Underwriting rules as a small Python class per product | A rules engine / DSL a risk analyst can edit without a deploy | Three known products, owned by engineering, is the right scope now; revisit if a non-engineering team needs to own thresholds independently |

## What was deferred entirely (mocked or scoped out)

- **Real third-party integrations.** Credit bureau, identity/KYC, fraud, and core
  banking are mocked behind stable interfaces — the orchestration, retry, and
  failure-handling logic is real; the HTTP calls at the bottom aren't. Swapping a
  mock for a real adapter is additive.
- **Production auth/RBAC on the dashboard.** A real deployment needs SSO and role
  separation (loan officer vs. compliance vs. admin); this exercise has a single
  operator role.
- **Document OCR / content verification.** Documents are tracked as
  present/missing/verified; nothing reads their contents.
- **A rules-authoring UI**, per the table above.
- **LLM-assisted broker email parsing.** Broker emails are semi-structured; a
  production version would likely use an LLM extraction step (parse → canonical
  schema, with a confidence score gating straight-through vs. flag-for-review)
  rather than a fixed template. Scoped out for time; the ingestion adapter
  boundary is designed so this swaps in cleanly.
- **A real observability stack.** Temporal Web UI + Postgres queries are the MVP
  here; production would add Prometheus/Grafana-style metrics on top.

## Retrospective — what I'd do differently with more time

- **Define specific alert thresholds and an actual on-call runbook**, not just
  "the visibility exists" — e.g. "stuck > 4h in ENRICHING with 3+ check failures
  → page X."
- **Load-test the batch path specifically** — the design reasons about 50K/month
  from first principles, but doesn't include an actual load test proving the
  aggregator-batch-spike case behaves as expected under real concurrency.
- **Get real distributions for provider latency/failure rates** before tuning
  retry policy constants, rather than using reasonable-looking placeholders.

## Future development roadmap

1. Split third-party check activities onto dedicated task queues with
   server-enforced rate limits, once real provider contracts and volumes are
   known.
2. Add the `SLAMonitorWorkflow` sweep + alerting on top of the existing
   Postgres `sla_deadline` tracking.
3. Real third-party + core banking integrations behind the existing adapter
   interfaces.
4. RBAC + SSO on the ops dashboard; audit-log access scoped to compliance role.
5. Rules-engine-backed `LoanProductPolicy` for risk-team self-service.
6. LLM-assisted broker email extraction with a confidence-gated review path.
7. Applicant-facing status page (read-only view of `get_status()` plus the
   Postgres-backed SLA countdown).
8. Metrics/alerting stack on top of Temporal + the audit table.
