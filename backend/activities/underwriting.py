from temporalio import activity

from backend.domain import UnderwritingDecision, UnderwritingInput
from backend.policies import get_product_policy


@activity.defn
async def evaluate_underwriting(input: UnderwritingInput) -> UnderwritingDecision:
    policy = get_product_policy(input.application.product_type)
    return policy.evaluate(input.application, input.credit, input.identity, input.fraud)
