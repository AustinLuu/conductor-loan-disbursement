"""Drop one aggregator batch file — a small JSON array of application
records, posted in one call, the same way a partner system's batch feed
would. Includes one deliberately invalid record and one deliberately
duplicated external_ref to demonstrate the "rejected" and
"duplicate_in_batch" paths. Stdlib only, so it runs without installing the
backend's own dependencies.

Usage:
  python ops/seed/submit_batch.py
"""
import json
import sys
import urllib.error
import urllib.request
import uuid

API_URL = "http://localhost:8000/ingest/batch"


def build_records() -> list[dict]:
    dup_ref = str(uuid.uuid4())
    return [
        {
            "external_ref": str(uuid.uuid4()),
            "product_type": "personal",
            "requested_amount": "9000",
            "applicant_name": "Alice Aggregator",
            "applicant_ssn": "111223333",
            "submitted_documents": ["government_id", "proof_of_income", "bank_statement"],
        },
        {
            "external_ref": str(uuid.uuid4()),
            "product_type": "auto",
            "requested_amount": "22000",
            "applicant_name": "Bob Batch",
            "applicant_ssn": "222334444",
            "submitted_documents": ["government_id", "proof_of_income", "vehicle_purchase_agreement"],
        },
        {
            "external_ref": "corrupt-record-1",
            "product_type": "personal",
            "requested_amount": "5000",
            "applicant_name": "Carol Corrupt",
            "applicant_ssn": "bad-ssn",  # deliberately invalid — demonstrates the "rejected" path
            "submitted_documents": [],
        },
        {
            "external_ref": dup_ref,
            "product_type": "debt_consolidation",
            "requested_amount": "13000",
            "applicant_name": "Dana Duplicate",
            "applicant_ssn": "333445555",
            "submitted_documents": ["government_id", "proof_of_income", "existing_debt_statement"],
        },
        {
            "external_ref": dup_ref,  # same ref as above — demonstrates the "duplicate_in_batch" path
            "product_type": "debt_consolidation",
            "requested_amount": "13000",
            "applicant_name": "Dana Duplicate",
            "applicant_ssn": "333445555",
            "submitted_documents": ["government_id", "proof_of_income", "existing_debt_statement"],
        },
    ]


def main() -> None:
    records = build_records()
    data = json.dumps(records).encode()
    request = urllib.request.Request(
        API_URL, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request) as response:
            results = json.load(response)
    except urllib.error.HTTPError as e:
        print(f"Batch submission failed: {e.code} {e.read().decode()}", file=sys.stderr)
        raise SystemExit(1)

    for record, result in zip(records, results):
        line = f"{record['external_ref']}: {result['status']}"
        if result["status"] == "accepted":
            line += f" (workflow_id={result['workflow_id']})"
        elif result["reason"]:
            line += f" — {result['reason']}"
        print(line)


if __name__ == "__main__":
    main()
