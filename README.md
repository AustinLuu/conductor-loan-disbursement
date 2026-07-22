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
