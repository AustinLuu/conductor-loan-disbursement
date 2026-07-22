"""Submit one test application through the portal channel — the API entry
point docker-compose brings up. Stdlib only, so it runs without installing
the backend's own dependencies.

Usage: python ops/seed/submit_portal_application.py
"""
import json
import sys
import urllib.error
import urllib.request

API_URL = "http://localhost:8000/applications"

PAYLOAD = {
    "product_type": "personal",
    "requested_amount": "15000",
    "applicant_name": "Jane Doe",
    "applicant_ssn": "123456789",
    "submitted_documents": ["government_id", "proof_of_income", "bank_statement"],
}


def main() -> None:
    data = json.dumps(PAYLOAD).encode()
    request = urllib.request.Request(
        API_URL, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request) as response:
            body = json.load(response)
    except urllib.error.HTTPError as e:
        print(f"Submission failed: {e.code} {e.read().decode()}", file=sys.stderr)
        raise SystemExit(1)

    print(f"Application submitted: {body['application_id']}")
    print(f"Workflow ID: {body['workflow_id']}")
    print(f"Watch it at: http://localhost:8233/namespaces/default/workflows/{body['workflow_id']}")


if __name__ == "__main__":
    main()
