# Conductor Take-Home — Documentation Index

**Exercise:** Loan Disbursement Orchestration (PocketHealth / Conductor case study)
**Author:** [Your name]
**Stack:** Python (FastAPI) + Temporal Python SDK + Postgres + React

This folder is the full documentation set for the take-home. It's organized the way a
real system would be documented — PRD first (what/why), system design second (the
architecture, mapped to the 6-step framework), TDD third (how it's actually built),
then user docs and a trade-offs/retro doc last.

| # | Doc | Purpose | Maps to PPT section |
|---|---|---|---|
| 01 | [PRD](./01-PRD.md) | Problem, users, requirements, success metrics | Requirements |
| 02 | [System Design](./02-system-design.md) | The 6-step design: requirements → entities → APIs → data flows → HLD/architecture → deep dives | Core Entities, APIs, Data Flows, HLD, Deep Dives |
| 03 | [TDD](./03-TDD.md) | Implementation-level detail: workflow/activity signatures, task queues, schemas, testing | Deep Dives / code walkthrough |
| 04 | [User Docs](./04-user-docs.md) | How operators, engineers, and compliance use the system | Supporting artifact |
| 05 | [Trade-offs, Retro & Future Work](./05-tradeoffs-and-future-work.md) | What was deferred, why, and what's next | Trade-offs / Retrospective |
| 06 | [Timeboxing & Approach](./06-timeboxing-and-approach.md) | How the exercise was scoped and paced | Timeboxing |

## Reading order

If you're reviewing this for the first time: **01 → 02 → 03**, then skim 04–06.
Diagrams live inline as Mermaid in doc 02 (and are exported as standalone images
under `/diagrams` for the slide deck).

## Repo layout

```
conductor-loan-disbursement/
├── docs/          ← this folder
├── backend/       ← FastAPI + Temporal workflows/activities (Python)
├── frontend/       ← Ops dashboard (React)
├── diagrams/       ← Exported PNG/SVG versions of the Mermaid diagrams
└── ops/            ← docker-compose.yml, local run scripts
```
