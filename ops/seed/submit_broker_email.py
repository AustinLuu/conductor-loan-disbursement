"""Submit one test application through the broker-email channel. A real
deployment would parse an inbound email into this shape (docs/05's deferred
"LLM-assisted broker email parsing" item); this script posts the
already-structured JSON directly, the same way that parsing step's output
would arrive. Stdlib only, so it runs without installing the backend's own
dependencies.

Usage:
  python ops/seed/submit_broker_email.py                    # fresh message_id each run
  python ops/seed/submit_broker_email.py --message-id X     # reuse an id, e.g. to test dedup
  python ops/seed/submit_broker_email.py --product-type debt_consolidation
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid

API_URL = "http://localhost:8000/ingest/broker-email"

# Mirrors each LoanProductPolicy.required_documents() (backend/policies/) —
# submitting a product's own required set is what makes the random-credit-
# score outcome the only variable, instead of also landing in
# AWAITING_DOCUMENTS.
REQUIRED_DOCUMENTS = {
    "personal": ["government_id", "proof_of_income", "bank_statement"],
    "auto": ["government_id", "proof_of_income", "vehicle_purchase_agreement"],
    "debt_consolidation": ["government_id", "proof_of_income", "existing_debt_statement"],
}


def build_payload(message_id: str, product_type: str) -> dict:
    return {
        "message_id": message_id,
        "broker_name": "Acme Brokers",
        "product_type": product_type,
        "requested_amount": "18000",
        "applicant_name": "John Smith",
        "applicant_ssn": "987654321",
        "submitted_documents": REQUIRED_DOCUMENTS[product_type],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--message-id",
        default=None,
        help="Reuse this id across runs to demonstrate duplicate-submission rejection.",
    )
    parser.add_argument(
        "--product-type",
        choices=sorted(REQUIRED_DOCUMENTS),
        default="personal",
        help="Which product's risk thresholds to submit against (default: personal).",
    )
    args = parser.parse_args()
    message_id = args.message_id or str(uuid.uuid4())

    data = json.dumps(build_payload(message_id, args.product_type)).encode()
    request = urllib.request.Request(
        API_URL, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request) as response:
            body = json.load(response)
    except urllib.error.HTTPError as e:
        print(f"Submission failed: {e.code} {e.read().decode()}", file=sys.stderr)
        raise SystemExit(1)

    print(f"message_id: {message_id}")
    print(f"Application submitted: {body['application_id']}")
    print(f"Workflow ID: {body['workflow_id']}")
    print(f"Watch it at: http://localhost:8233/namespaces/default/workflows/{body['workflow_id']}")


if __name__ == "__main__":
    main()
