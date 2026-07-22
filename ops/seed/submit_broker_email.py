"""Submit one test application through the broker-email channel. A real
deployment would parse an inbound email into this shape (docs/05's deferred
"LLM-assisted broker email parsing" item); this script posts the
already-structured JSON directly, the same way that parsing step's output
would arrive. Stdlib only, so it runs without installing the backend's own
dependencies.

Usage:
  python ops/seed/submit_broker_email.py                    # fresh message_id each run
  python ops/seed/submit_broker_email.py --message-id X     # reuse an id, e.g. to test dedup
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid

API_URL = "http://localhost:8000/ingest/broker-email"


def build_payload(message_id: str) -> dict:
    return {
        "message_id": message_id,
        "broker_name": "Acme Brokers",
        "product_type": "personal",
        "requested_amount": "18000",
        "applicant_name": "John Smith",
        "applicant_ssn": "987654321",
        "submitted_documents": ["government_id", "proof_of_income", "bank_statement"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--message-id",
        default=None,
        help="Reuse this id across runs to demonstrate duplicate-submission rejection.",
    )
    args = parser.parse_args()
    message_id = args.message_id or str(uuid.uuid4())

    data = json.dumps(build_payload(message_id)).encode()
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
