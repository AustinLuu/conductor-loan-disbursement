# User Docs

## For Loan Ops / Reviewers

**Where to look:** the ops dashboard's **Review Queue** shows every application
currently waiting on a human decision, sorted by SLA risk (most urgent first).

**What you're seeing:**
- **Reason for referral** — why this landed with you instead of being
  auto-decided (e.g. "risk score in gray zone," "identity check ambiguous").
- **Full check results** — credit, identity, and fraud results, plus the
  underwriting rule trace so you can see exactly which policy thresholds fired.
- **SLA countdown** — time remaining against the 48-hour target.

**Making a decision:** Approve, Decline, or Escalate.
- *Approve* / *Decline* resolve the application directly — the system resumes
  automatically (approve routes to disbursement, decline closes the case).
- *Escalate* takes an application **out of the automated pipeline entirely** —
  use this for anything that needs handling outside this system (e.g. a fraud
  referral to a specialist team). This is a terminal state here; follow-up
  happens in whatever process your team uses off-platform.

**"Needs Human Review" vs. "Escalated" — what's the difference?** "Needs Human
Review" is where your queue lives — the application is paused, waiting on you,
still inside the automated pipeline. "Escalated" is what happens *after* you
decide this case shouldn't be resolved inside the pipeline at all. You move
applications from the first to the second by choosing Escalate.

**If you don't act in time:** applications that sit in review past a timeout are
automatically moved to Escalated so nothing sits in limbo indefinitely — you'll
see these flagged distinctly from ones you actively escalated.

## For Engineering

**Running locally:**
```bash
cd ops && docker compose up
```
Brings up: Temporal dev server (Web UI at `localhost:8233`), Postgres, the worker
process, the FastAPI backend, and the ops dashboard (`localhost:5173`).

**Submitting a test application per channel:**
```bash
ops/seed/submit_portal.sh          # simulates a portal submission
ops/seed/submit_broker_email.sh    # simulates a broker email payload
ops/seed/submit_batch.sh           # drops a small aggregator batch file
```

**Watching it work:** the Temporal Web UI shows the running workflow, its event
history, pending activities, and any retries in real time — this is the fastest
way to see *why* something is stuck without adding custom instrumentation.

**Adding a new loan product:** implement `LoanProductPolicy` in
`backend/policies/`, register it in the policy registry, add its required
documents/thresholds. No change to `LoanApplicationWorkflow` itself.

**Adding a new third-party provider:** add an adapter in `backend/adapters/` and
an activity that calls it, registered on the shared `loan-processing` task queue
with its own `RetryPolicy`. If a provider's rate limits start conflicting with
others under real load, that's the point to split it onto a dedicated task queue
— see [Trade-offs](./05-tradeoffs-and-future-work.md).

## For Compliance / Audit

**Pulling a full audit trail for one application:**
`GET /audit/{application_id}` returns every recorded decision — automated and
human — with actor, timestamp, and the underlying reasoning (rule trace or
reviewer notes). This is backed by the Postgres `audit_events` table; if an
entry is ever in question, the Temporal Web UI's event history for that
application's workflow ID is the tamper-evident source of record it was written
from.

**Querying across applications:** the same table supports standard SQL filtering
(product, date range, decision outcome, reviewer) for periodic compliance
reporting — this doesn't require touching Temporal directly.
