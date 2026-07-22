// SLA countdown/risk, computed entirely from timestamps already on the
// Application row (submitted_at, sla_deadline) — never from a Temporal
// query. See docs/02-system-design.md §3.2 and docs/03-TDD.md for why a
// live countdown can't safely come from a workflow query.

// ponytail: fixed 25%-of-window heuristic for "at risk" — no per-product
// threshold in the docs. Revisit if ops wants tunable bands per product.
const AT_RISK_FRACTION = 0.25;

export function computeSlaStatus(submittedAt, slaDeadline, now = new Date()) {
  const submitted = new Date(submittedAt);
  const deadline = new Date(slaDeadline);
  const totalMs = deadline - submitted;
  const remainingMs = deadline - now;

  let level;
  if (remainingMs <= 0) {
    level = "breached";
  } else if (totalMs > 0 && remainingMs / totalMs < AT_RISK_FRACTION) {
    level = "at_risk";
  } else {
    level = "on_track";
  }

  return { remainingMs, level, label: formatRemaining(remainingMs) };
}

export function formatRemaining(remainingMs) {
  const overdue = remainingMs < 0;
  const abs = Math.abs(remainingMs);
  const totalMinutes = Math.floor(abs / 60000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  const text = `${hours}h ${minutes}m`;
  return overdue ? `Overdue by ${text}` : `${text} left`;
}
