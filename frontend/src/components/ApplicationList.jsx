import { useEffect, useState } from "react";
import { listApplications } from "../api.js";
import { computeSlaStatus } from "../slaRisk.js";
import { useNow } from "../useNow.js";

const RISK_LABEL = { on_track: "On track", at_risk: "At risk", breached: "Breached" };

export default function ApplicationList() {
  const [applications, setApplications] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const now = useNow();

  useEffect(() => {
    let cancelled = false;
    listApplications()
      .then((data) => { if (!cancelled) setApplications(data); })
      .catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) return <p>Loading applications…</p>;
  if (error) return <div className="error-banner">{error}</div>;
  if (applications.length === 0) return <p className="empty-state">No applications yet.</p>;

  return (
    <table>
      <thead>
        <tr>
          <th>Application</th>
          <th>Product</th>
          <th>Amount</th>
          <th>Status</th>
          <th>Submitted</th>
          <th>SLA</th>
        </tr>
      </thead>
      <tbody>
        {applications.map((app) => {
          const sla = computeSlaStatus(app.submitted_at, app.sla_deadline, now);
          return (
            <tr key={app.id}>
              <td title={app.id}>{app.id.slice(0, 8)}</td>
              <td>{app.product_type}</td>
              <td>${app.requested_amount}</td>
              <td>{app.status}</td>
              <td>{new Date(app.submitted_at).toLocaleString()}</td>
              <td>
                <span className={`badge ${sla.level}`}>{RISK_LABEL[sla.level]}</span>{" "}
                {sla.label}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
