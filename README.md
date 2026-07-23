# Conductor Loan Disbursement Orchestration

Temporal-orchestrated loan application pipeline: ingest from portal/broker-email/
aggregator-batch channels, validate, run credit/identity/fraud checks, underwrite
(auto or human review), disburse — with a React ops dashboard and a full audit trail.

**Start here for the full write-up:** [docs/00-README.md](./docs/00-README.md) —
indexes the PRD, system design, TDD, user docs, and trade-offs docs, with a
suggested reading order.

## Run it

```bash
cd ops
docker compose up
```

Brings up Postgres, a Temporal dev server, the worker, the FastAPI backend, and the
React dashboard. Once healthy:

| Thing | URL |
|---|---|
| API | http://localhost:8000 |
| Ops dashboard | http://localhost:5173 |
| Temporal Web UI (workflow state, retries) | http://localhost:8233 |

Submit a test application through any channel using the seed scripts (stdlib only,
no install needed):

```bash
python ops/seed/submit_portal_application.py
python ops/seed/submit_broker_email.py
python ops/seed/submit_batch.py
```

Then watch it move through the Temporal Web UI and the dashboard.

## Exercising every workflow path

The state machine (docs/03-TDD.md §3.1) has more paths than the happy-path seed
scripts hit by default. This is a manual runbook for driving each of them
against a running `docker compose up` stack, using `curl` and the seed
scripts.

**On Windows PowerShell**, none of the `curl ...` commands below will work
as-is: PowerShell's built-in `curl` is an alias for `Invoke-WebRequest` and
rejects `-H`/`-d` outright, and even calling `curl.exe` explicitly doesn't
fully fix it — PowerShell mangles embedded double-quotes when it builds the
argument list for *any* native executable, so a JSON body like `-d
'{"key":"value"}'` arrives corrupted regardless of the exe. The reliable fix
is `Invoke-RestMethod` with a hashtable, since it never shells out to a
native process at all — each POST example below includes the equivalent.

Single-application outcomes are driven by a random mock credit score
(560–800) against per-product thresholds — each submission independently
rolls the dice, so resubmit until you hit the outcome you want:

| Product | Decline (score <) | Refer to review | Auto-approve (score ≥) |
|---|---|---|---|
| `personal` | 580 | 580–639 | 640 |
| `auto` | 560 | 560–619 | 620 |
| `debt_consolidation` | 600 | 600–659 | 660 |

`GET http://localhost:8000/applications/{id}` shows the current `status` at
any point.

**`auto` can never decline.** The mock credit score generator's floor
(`random.randint(560, 800)`) exactly equals `auto`'s `decline_below`
threshold, so its `score < 560` check can never be true — confirmed by 30
live submissions, 0 declines. Not a rare outcome to keep resubmitting for;
it's dead code under the current mocks. `personal` and `debt_consolidation`
don't have this problem (their decline thresholds sit strictly above the
score floor).

### 1–3. Auto-approve / auto-decline / refer — any product, portal or broker-email

```bash
python ops/seed/submit_portal_application.py                                  # --external-ref X to reuse an id
python ops/seed/submit_broker_email.py                                        # --message-id X to reuse an id
python ops/seed/submit_portal_application.py --product-type auto              # or debt_consolidation
python ops/seed/submit_broker_email.py --product-type debt_consolidation      # or auto
```
Both default to `personal`; `--product-type` submits the right required
documents for whichever product you pick, so the only variable left is the
random credit score. Resubmit (unique ref each time) until you've seen all
three outcomes for a product — decline is the rarest band for all three
(~8% per try) — expect more tries for that one.

### 4–6. Human Approve / Decline / Escalate

1. Get an application into `NEEDS_HUMAN_REVIEW` (path 1–3, refer outcome).
2. `GET http://localhost:8000/reviews` → find its `review_id` (`status: "pending"`).
3. Decide it:
   ```bash
   curl.exe -s -X POST http://localhost:8000/reviews/{review_id}/decision \
     -H "Content-Type: application/json" \
     -d '{"outcome":"approve","reason":"looks fine","reviewer":"you","notes":""}'
   ```
   PowerShell:
   ```powershell
   $body = @{ outcome = "approve"; reason = "looks fine"; reviewer = "you"; notes = "" } | ConvertTo-Json
   Invoke-RestMethod -Uri "http://localhost:8000/reviews/{review_id}/decision" -Method Post -ContentType "application/json" -Body $body
   ```
   `outcome` is `approve` | `decline` | `escalate` → application status becomes
   `FUNDED` | `DECLINED` | `ESCALATED` respectively.

### 7–8. `AWAITING_DOCUMENTS` → resume

Personal loans require `government_id`, `proof_of_income`, `bank_statement`.
Omit one at submission to land in `AWAITING_DOCUMENTS`:
```bash
curl.exe -s -X POST http://localhost:8000/applications -H "Content-Type: application/json" -d '{
  "external_ref": "doc-test-1", "product_type": "personal", "requested_amount": "15000",
  "applicant_name": "Jane Doe", "applicant_ssn": "123456789",
  "submitted_documents": ["government_id", "proof_of_income"]
}'
```
PowerShell:
```powershell
$body = @{
    external_ref = "doc-test-1"; product_type = "personal"; requested_amount = "15000"
    applicant_name = "Jane Doe"; applicant_ssn = "123456789"
    submitted_documents = @("government_id", "proof_of_income")
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/applications" -Method Post -ContentType "application/json" -Body $body
```
Then resume it (works regardless of which channel created the application —
only needs the `application_id`):
```bash
curl.exe -s -X POST http://localhost:8000/applications/{id}/documents \
  -H "Content-Type: application/json" -d '{"doc_type": "bank_statement", "storage_ref": "test"}'
```
PowerShell:
```powershell
$body = @{ doc_type = "bank_statement"; storage_ref = "test" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/applications/{id}/documents" -Method Post -ContentType "application/json" -Body $body
```

### 9. `AWAITING_DOCUMENTS` → `DECLINED` (doc timeout, abandoned) — not practical live

Waits on the 48h SLA. To see it: temporarily shrink `_SLA_HOURS` near the top
of `backend/workflows/loan_application_workflow.py`, rebuild the worker
(`docker compose up -d --build worker`), submit a missing-doc application
(path 7) and don't submit the doc. **Revert the constant and rebuild again
afterward** — don't leave this changed, and don't run this concurrently with
anything else exercising the stack (see the chaos-testing note below).

### 10. `check_unavailable` → `NEEDS_HUMAN_REVIEW`

All third-party checks (`credit`/`identity`/`fraud`/`disbursement`) share one
chaos knob, `MOCK_FAILURE_RATE` (env var on the `worker` service, default
`0.0`), read at runtime — no rebuild needed, just a container recreate. **Run
this alone, not alongside other testing** — it affects every in-flight
workflow on the shared stack for as long as it's set.

1. In `ops/docker-compose.yml`, add `MOCK_FAILURE_RATE: "1"` to the `worker`
   service's `environment:` block.
2. `docker compose up -d worker` (from `ops/`, **no** `--build` — the var is
   read at runtime, rebuilding would also bake in any other uncommitted
   changes on disk).
3. Submit any application — at rate `1`, every check exhausts its 5 retries
   (budget ~1–2 minutes of polling). It lands in `NEEDS_HUMAN_REVIEW` with
   `reason: "check_unavailable"` and the Review Queue's check-results panel
   shows the "no automated results" fallback instead of real numbers.

### 11. `FUNDING` → `ESCALATED` (disbursement fails irrecoverably)

With `MOCK_FAILURE_RATE=1` still set from path 10: take the item from path 10
and **Approve** it (path 4's mechanism). Disbursement also exhausts its
retries under the same rate, landing the application in `ESCALATED` (reason
`disbursement_failed`, visible via `GET /audit/{id}`) instead of `FUNDED`.

**Clean up:** remove the `MOCK_FAILURE_RATE` line from
`ops/docker-compose.yml`, `docker compose up -d worker` again (no `--build`)
— with it left at `1`, nothing will ever fund or clear a check again.

### 12. Review timeout → `ESCALATED` — not practical live

Same SLA-timeout caveat as path 9. Shrink `_SLA_HOURS`, rebuild the worker,
get an item into `NEEDS_HUMAN_REVIEW` (path 3) and don't decide it — it flips
to `ESCALATED` (`reason: "review_timeout"`) once the shortened window
elapses. Revert and rebuild again afterward.

### 13–15. Aggregator batch — per-record edge cases

```bash
python ops/seed/submit_batch.py
```
One call, five records, prints one line per result. Built in on purpose:
- `rejected` — a record with a malformed SSN (fails validation, no workflow started).
- `duplicate_in_batch` — two records in the same call share an `external_ref`; the second is flagged, not started.
- `accepted` — the other three, each starts a real `LoanApplicationWorkflow`.

For cross-call `duplicate` (an `external_ref` that collided with a
*previously* accepted record, not one in the same call), POST the same
single-record batch twice:
```bash
curl.exe -s -X POST http://localhost:8000/ingest/batch -H "Content-Type: application/json" -d '[{
  "external_ref": "cross-call-dup", "product_type": "personal", "requested_amount": "9000",
  "applicant_name": "Test Dup", "applicant_ssn": "111223333",
  "submitted_documents": ["government_id", "proof_of_income", "bank_statement"]
}]'
```
PowerShell (the endpoint expects a JSON *array* — wrap in `@()` at the call
site or `ConvertTo-Json` silently collapses a single-element array to a bare
object):
```powershell
$records = @(
    @{
        external_ref = "cross-call-dup"; product_type = "personal"; requested_amount = "9000"
        applicant_name = "Test Dup"; applicant_ssn = "111223333"
        submitted_documents = @("government_id", "proof_of_income", "bank_statement")
    }
)
$body = ConvertTo-Json @($records)
Invoke-RestMethod -Uri "http://localhost:8000/ingest/batch" -Method Post -ContentType "application/json" -Body $body
```
First call: `status: "accepted"`. Second call, identical body: `status: "duplicate"`.

### 16–17. Duplicate-submission rejection (409)

```bash
python ops/seed/submit_broker_email.py --message-id dup-test-1
python ops/seed/submit_broker_email.py --message-id dup-test-1   # 409, message_id already exists

python ops/seed/submit_portal_application.py --external-ref dup-test-2
python ops/seed/submit_portal_application.py --external-ref dup-test-2   # 409, external_ref already exists
```

## Run tests locally (without Docker)

```bash
pip install -r requirements.txt
pytest

cd frontend
npm install
npm test
```

## Repo layout

```
backend/    FastAPI + Temporal workflows/activities (Python)
frontend/   Ops dashboard (React + Vite)
docs/       PRD, system design, TDD, user docs, trade-offs — see docs/00-README.md
diagrams/   Exported versions of the Mermaid diagrams in docs/02-system-design.md
ops/        docker-compose.yml, Dockerfile, seed scripts
```
