"""Grant catalog — aggregates all grant data sources."""

from __future__ import annotations

from typing import Dict, List, Optional

from src.billing.grants.models import Grant
from src.billing.grants.federal_tax_credits import get_federal_tax_credit_grants
from src.billing.grants.federal_grants import get_federal_grants
from src.billing.grants.sba_financing import get_sba_financing_grants
from src.billing.grants.usda_programs import get_usda_grants
from src.billing.grants.state_incentives import get_state_incentive_grants
from src.billing.grants.utility_programs import get_utility_program_grants
from src.billing.grants.pace_financing import get_pace_financing_grants
from src.billing.grants.green_banks import get_green_bank_grants
from src.billing.grants.espc import get_espc_grants
from src.billing.grants.rd_tax_credits import get_rd_tax_credit_grants

_CATALOG: Dict[str, Grant] = {}


def get_all_grants() -> List[Grant]:
    """Return complete grant catalog, building lazily on first call."""
    if not _CATALOG:
        all_grants = (
            get_federal_tax_credit_grants()
            + get_federal_grants()
            + get_sba_financing_grants()
            + get_usda_grants()
            + get_state_incentive_grants()
            + get_utility_program_grants()
            + get_pace_financing_grants()
            + get_green_bank_grants()
            + get_espc_grants()
            + get_rd_tax_credit_grants()
        )
        for g in all_grants:
            _CATALOG[g.id] = g
    return list(_CATALOG.values())


def get_grant_by_id(grant_id: str) -> Optional[Grant]:
    """Return grant by ID or None if not found."""
    get_all_grants()  # ensure catalog is loaded
    return _CATALOG.get(grant_id)
