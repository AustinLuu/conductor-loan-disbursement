import { useEffect, useState } from "react";
import { listReviews, getApplication, submitReviewDecision } from "../api.js";
import { computeSlaStatus } from "../slaRisk.js";
import { useNow } from "../useNow.js";

const RISK_LABEL = { on_track: "On track", at_risk: "At risk", breached: "Breached" };

function CheckResults({ auditEvents }) {
  const decision = auditEvents.find((e) => e.event_type === "underwriting_decision");
  if (!decision) {
    return <p className="meta">No automated check results recorded for this case.</p>;
  }
  const { credit, identity, fraud } = decision.detail;
  return (
    <div className="check-grid">
      <div>
        <strong>Credit</strong>
        <pre>{JSON.stringify(credit, null, 2)}</pre>
      </div>
      <div>
        <strong>Identity</strong>
        <pre>{JSON.stringify(identity, null, 2)}</pre>
      </div>
      <div>
        <strong>Fraud</strong>
        <pre>{JSON.stringify(fraud, null, 2)}</pre>
      </div>
    </div>
  );
}

function DecisionForm({ reviewId, onDecided }) {
  const [reviewer, setReviewer] = useState("");
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  async function decide(outcome) {
    setSubmitting(true);
    setError(null);
    try {
      await submitReviewDecision(reviewId, { outcome, reason, reviewer, notes });
      onDecided();
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  const canSubmit = !submitting && reviewer.trim() && reason.trim();

  return (
    <form className="decision-form" onSubmit={(e) => e.preventDefault()}>
      {error && <div className="error-banner">{error}</div>}
      <input
        placeholder="Reviewer name"
        value={reviewer}
        onChange={(e) => setReviewer(e.target.value)}
        required
      />
      <input
        placeholder="Reason for decision"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        required
      />
      <textarea
        placeholder="Notes (optional)"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        rows={1}
      />
      <div className="actions">
        <button type="button" className="approve" disabled={!canSubmit} onClick={() => decide("approve")}>
          Approve
        </button>
        <button type="button" className="decline" disabled={!canSubmit} onClick={() => decide("decline")}>
          Decline
        </button>
        <button type="button" className="escalate" disabled={!canSubmit} onClick={() => decide("escalate")}>
          Escalate
        </button>
      </div>
    </form>
  );
}

export default function ReviewQueue() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [partialError, setPartialError] = useState(null);
  const [loading, setLoading] = useState(true);
  // ponytail: true until the first fetch attempt finishes (success or failure), then
  // never reset — distinguishes "nothing rendered yet" from "refetching in the background"
  // so a post-decision refresh doesn't unmount every other card's in-progress form.
  const [initialLoad, setInitialLoad] = useState(true);
  const now = useNow();

  // Each call owns its own cancellation scope so a stale invocation (e.g. React
  // StrictMode's double-invoke on mount) can never clobber state after a fresher
  // one has already resolved. refresh() stays a plain function other call sites
  // (DecisionForm's onDecided) can invoke directly; the mount effect uses the
  // returned canceller as its cleanup.
  function refresh() {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listReviews()
      .then((reviews) =>
        Promise.allSettled(
          reviews.map((review) =>
            getApplication(review.application_id).then((application) => ({ review, application }))
          )
        ).then((results) => {
          if (cancelled) return;
          const loaded = [];
          const failures = [];
          results.forEach((result, i) => {
            if (result.status === "fulfilled") {
              loaded.push(result.value);
            } else {
              failures.push(
                `application ${reviews[i].application_id.slice(0, 8)}: ${result.reason.message}`
              );
            }
          });
          setItems(loaded);
          setPartialError(
            failures.length === 0
              ? null
              : `${failures.length} of ${results.length} review item${
                  results.length === 1 ? "" : "s"
                } failed to load — ${failures.join("; ")}`
          );
        })
      )
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
          setInitialLoad(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }

  useEffect(refresh, []);

  if (initialLoad) return <p>Loading review queue…</p>;
  if (error && items.length === 0) return <div className="error-banner">{error}</div>;
  if (items.length === 0 && !loading) return <p className="empty-state">Review queue is empty.</p>;

  const sorted = [...items].sort(
    (a, b) => new Date(a.application.sla_deadline) - new Date(b.application.sla_deadline)
  );

  return (
    <>
      {loading && <p className="refresh-note">Refreshing…</p>}
      {error && <div className="error-banner">{error}</div>}
      {partialError && <div className="error-banner">{partialError}</div>}
      {sorted.map(({ review, application }) => {
        const sla = computeSlaStatus(application.submitted_at, application.sla_deadline, now);
        return (
          <div className="review-card" key={review.id}>
            <h3>
              {application.product_type} — ${application.requested_amount}{" "}
              <span className={`badge ${sla.level}`}>{RISK_LABEL[sla.level]}</span>
            </h3>
            <p className="meta">
              Application {application.id.slice(0, 8)} · Referred: {review.reason} · {sla.label}
            </p>
            <CheckResults auditEvents={application.audit_events} />
            <DecisionForm reviewId={review.id} onDecided={refresh} />
          </div>
        );
      })}
    </>
  );
}
