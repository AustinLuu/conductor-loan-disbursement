import { test } from "node:test";
import assert from "node:assert/strict";
import { computeSlaStatus, formatRemaining } from "./slaRisk.js";

test("on_track when most of the window remains", () => {
  const submitted = "2026-01-01T00:00:00Z";
  const deadline = "2026-01-03T00:00:00Z"; // 48h window
  const now = new Date("2026-01-01T01:00:00Z"); // 1h in, 47h left
  assert.equal(computeSlaStatus(submitted, deadline, now).level, "on_track");
});

test("at_risk once under 25% of the window remains", () => {
  const submitted = "2026-01-01T00:00:00Z";
  const deadline = "2026-01-03T00:00:00Z"; // 48h window
  const now = new Date("2026-01-02T15:00:00Z"); // 9h left of 48h = 18.75%
  assert.equal(computeSlaStatus(submitted, deadline, now).level, "at_risk");
});

test("breached once past the deadline", () => {
  const submitted = "2026-01-01T00:00:00Z";
  const deadline = "2026-01-03T00:00:00Z";
  const now = new Date("2026-01-03T00:05:00Z");
  const result = computeSlaStatus(submitted, deadline, now);
  assert.equal(result.level, "breached");
  assert.match(result.label, /^Overdue by/);
});

test("formatRemaining renders hours and minutes", () => {
  assert.equal(formatRemaining(90 * 60000), "1h 30m left");
  assert.equal(formatRemaining(-5 * 60000), "Overdue by 0h 5m");
});
