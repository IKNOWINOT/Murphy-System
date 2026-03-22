# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from src.billing.grants.submission.models import SubmissionStep


class BasePortalInstructions(ABC):
    @abstractmethod
    def generate_steps(self, application_data: dict) -> List[SubmissionStep]:
        ...
