"""Submit one test application through the portal channel — the API entry
point docker-compose brings up. Stdlib only, so it runs without installing
the backend's own dependencies.

Usage:
  python ops/seed/submit_portal_application.py                  # fresh external_ref each run
  python ops/seed/submit_portal_application.py --external-ref X # reuse a ref, e.g. to test dedup
  python ops/seed/submit_portal_application.py --product-type auto
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid

API_URL = "http://localhost:8000/applications"

# Mirrors each LoanProductPolicy.required_documents() (backend/policies/) —
# submitting a product's own required set is what makes the random-credit-
# score outcome the only variable, instead of also landing in
# AWAITING_DOCUMENTS.
REQUIRED_DOCUMENTS = {
    "personal": ["government_id", "proof_of_income", "bank_statement"],
    "auto": ["government_id", "proof_of_income", "vehicle_purchase_agreement"],
    "debt_consolidation": ["government_id", "proof_of_income", "existing_debt_statement"],
}


def build_payload(external_ref: str, product_type: str) -> dict:
    return {
        "external_ref": external_ref,
        "product_type": product_type,
        "requested_amount": "15000",
        "applicant_name": "Jane Doe",
        "applicant_ssn": "123456789",
        "submitted_documents": REQUIRED_DOCUMENTS[product_type],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--external-ref",
        default=None,
        help="Reuse this ref across runs to demonstrate duplicate-submission rejection.",
    )
    parser.add_argument(
        "--product-type",
        choices=sorted(REQUIRED_DOCUMENTS),
        default="personal",
        help="Which product's risk thresholds to submit against (default: personal).",
    )
    args = parser.parse_args()
    external_ref = args.external_ref or str(uuid.uuid4())

    data = json.dumps(build_payload(external_ref, args.product_type)).encode()
    request = urllib.request.Request(
        API_URL, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request) as response:
            body = json.load(response)
    except urllib.error.HTTPError as e:
        print(f"Submission failed: {e.code} {e.read().decode()}", file=sys.stderr)
        raise SystemExit(1)

    print(f"external_ref: {external_ref}")
    print(f"Application submitted: {body['application_id']}")
    print(f"Workflow ID: {body['workflow_id']}")
    print(f"Watch it at: http://localhost:8233/namespaces/default/workflows/{body['workflow_id']}")


if __name__ == "__main__":
    main()
