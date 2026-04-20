"""
Form definitions registry.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

from typing import Dict, List, Optional

from src.billing.grants.form_filler.form_definitions.base import BaseFormDefinition
from src.billing.grants.form_filler.form_definitions.sbir_phase1 import SBIRPhase1Form
from src.billing.grants.form_filler.form_definitions.sttr_phase1 import STTRPhase1Form
from src.billing.grants.form_filler.form_definitions.nsf_sbir import NSFSBIRForm
from src.billing.grants.form_filler.form_definitions.sam_gov import SAMGovForm
from src.billing.grants.form_filler.form_definitions.grants_gov import GrantsGovForm
from src.billing.grants.form_filler.form_definitions.sba_microloan import SBAMicroloanForm
from src.billing.grants.form_filler.form_definitions.energy_trust import EnergyTrustForm
from src.billing.grants.form_filler.form_definitions.generic_grant import GenericGrantForm

FORM_REGISTRY: Dict[str, BaseFormDefinition] = {
    "sbir_phase1": SBIRPhase1Form(),
    "sbir_phase2": SBIRPhase1Form(),
    "sttr_phase1": STTRPhase1Form(),
    "nsf_sbir": NSFSBIRForm(),
    "sam_gov": SAMGovForm(),
    "grants_gov": GrantsGovForm(),
    "sba_microloan": SBAMicroloanForm(),
    "energy_trust": EnergyTrustForm(),
    "generic_grant": GenericGrantForm(),
}


def get_form(form_id: str) -> Optional[BaseFormDefinition]:
    return FORM_REGISTRY.get(form_id)


def list_forms() -> List[BaseFormDefinition]:
    return list(FORM_REGISTRY.values())


__all__ = [
    "FORM_REGISTRY", "get_form", "list_forms", "BaseFormDefinition",
    "SBIRPhase1Form", "STTRPhase1Form", "NSFSBIRForm", "SAMGovForm",
    "GrantsGovForm", "SBAMicroloanForm", "EnergyTrustForm", "GenericGrantForm",
]
