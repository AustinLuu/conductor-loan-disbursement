from backend.domain import ProductType
from backend.policies.auto import AutoLoanPolicy
from backend.policies.base import LoanProductPolicy
from backend.policies.debt_consolidation import DebtConsolidationPolicy
from backend.policies.personal import PersonalLoanPolicy

_REGISTRY: dict[ProductType, LoanProductPolicy] = {
    ProductType.PERSONAL: PersonalLoanPolicy(),
    ProductType.AUTO: AutoLoanPolicy(),
    ProductType.DEBT_CONSOLIDATION: DebtConsolidationPolicy(),
}


def get_product_policy(product_type: ProductType | str) -> LoanProductPolicy:
    return _REGISTRY[ProductType(product_type)]
