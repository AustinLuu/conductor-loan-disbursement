from temporalio import activity

from backend.adapters import credit_bureau, fraud_provider, identity_provider
from backend.domain import ApplicationInput, CheckResult


@activity.defn
async def fetch_credit_report(application: ApplicationInput) -> CheckResult:
    return await credit_bureau.fetch_credit_report(application)


@activity.defn
async def verify_identity(application: ApplicationInput) -> CheckResult:
    return await identity_provider.verify_identity(application)


@activity.defn
async def run_fraud_check(application: ApplicationInput) -> CheckResult:
    return await fraud_provider.run_fraud_check(application)
