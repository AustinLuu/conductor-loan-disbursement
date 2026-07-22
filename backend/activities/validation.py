from temporalio import activity

from backend.domain import ApplicationInput, ValidationResult
from backend.policies import get_product_policy


@activity.defn
async def validate_application(application: ApplicationInput) -> ValidationResult:
    required = get_product_policy(application.product_type).required_documents()
    missing = [doc for doc in required if doc not in application.submitted_documents]
    return ValidationResult(missing_documents=missing)
