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
  const [loading, setLoading] = useState(true);
  const now = useNow();

  function refresh() {
    setLoading(true);
    setError(null);
    listReviews()
      .then((reviews) =>
        Promise.all(
          reviews.map(async (review) => ({
            review,
            application: await getApplication(review.application_id),
          }))
        )
      )
      .then(setItems)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, []);

  if (loading) return <p>Loading review queue…</p>;
  if (error) return <div className="error-banner">{error}</div>;
  if (items.length === 0) return <p className="empty-state">Review queue is empty.</p>;

  const sorted = [...items].sort(
    (a, b) => new Date(a.application.sla_deadline) - new Date(b.application.sla_deadline)
  );

  return (
    <>
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
