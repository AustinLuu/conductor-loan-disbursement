# Timeboxing & Approach

The case study asks for a 2-hour timebox. This doc covers two things honestly and
separately: **(A)** how I'd have scoped this if I'd stopped at 2 hours, because
disciplined scoping under a hard deadline is itself part of what this exercise is
testing, and **(B)** what I chose to extend afterward, using additional prep time
ahead of this final round, and why.

## A. The disciplined 2-hour version

If I were stopping at the 2-hour mark, here's what I'd prioritize and cut:

| Time | Focus | Cut to make it fit |
|---|---|---|
| 0:00–0:20 | Requirements + state machine on paper | No polished doc — a whiteboard-style state diagram |
| 0:20–0:50 | `LoanApplicationWorkflow` core happy path (validate → enrich → underwrite → fund) with mocked activities | One channel implemented for real (portal); broker email and aggregator batch **described**, not built |
| 0:50–1:10 | Human-in-the-loop signal/wait for review, with a timeout | No dashboard — a script that sends the signal via the Temporal CLI |
| 1:10–1:30 | One diagram (architecture) + one diagram (state machine) | Mermaid only, no exported images |
| 1:30–1:50 | A single design doc covering requirements → architecture → trade-offs in one pass | No separate PRD/TDD/user-docs split |
| 1:50–2:00 | Trade-offs section: explicitly list what's mocked/deferred | — |

The 2-hour version's job is to prove the *orchestration model* is right — a real
workflow, a real signal-based pause/resume, mocked-but-realistic third-party
activities — not to prove a full product exists. That's the right scope for a
2-hour box: depth on the one thing (Temporal) the exercise is actually testing,
breadth deliberately sacrificed everywhere else. It's also, not coincidentally,
close to what the actual build below turned into architecturally — a single task
queue, a single set of retry policies, no scheduled monitor workflow. The
extension added breadth and polish, not architectural complexity.

## B. What I extended, and why

Given this is being presented directly to the CTO and Director of Engineering as
part of a final round — not submitted cold — I used additional time beyond the
suggested box to take the same core design further: a working end-to-end app
across all three ingestion channels, the full doc set (PRD/TDD/user docs/trade-
offs), and a presentation built to walk through the system design process
explicitly rather than just hand over a repo. The underlying architecture and
trade-off reasoning are unchanged from what a disciplined 2-hour pass would have
produced — the extension is in breadth (all three channels, a real UI, fuller
docs) and polish (diagrams as standalone assets, a structured deck), not in a
different design.

**Phase breakdown for the extended build:**

| Phase | Focus |
|---|---|
| 1 | System design pass — requirements, entities, state machine, Temporal architecture (docs 01–03) |
| 2 | Backend — workflows, activities, mocked adapters, FastAPI, Postgres schema |
| 3 | Frontend — ops dashboard (review queue, application list, SLA-risk view) |
| 4 | Diagrams — exported standalone versions of the Mermaid diagrams for the deck |
| 5 | Presentation — assembled last, pulling directly from docs 01–05 so the deck and the artifacts agree with each other |

I'm noting this split explicitly rather than presenting the extended version as
if it were produced inside the original 2-hour window — the panel should know
which parts reflect the disciplined exercise and which reflect additional
investment made specifically for this final round.
