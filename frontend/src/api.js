const BASE = "/api";

async function request(path, options) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${options?.method || "GET"} ${path} failed: ${res.status} ${body}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export function listApplications() {
  return request("/applications");
}

export function getApplication(applicationId) {
  return request(`/applications/${applicationId}`);
}

export function listReviews() {
  return request("/reviews");
}

export function submitReviewDecision(reviewId, decision) {
  return request(`/reviews/${reviewId}/decision`, {
    method: "POST",
    body: JSON.stringify(decision),
  });
}
