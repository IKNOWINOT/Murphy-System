"""Recursion Stability Formula utilities"""
from dataclasses import dataclass

@dataclass
class StabilityMetrics:
    P_ETC: float  # predicted execution-time confidence (0-1)
    M_avail: float  # memory availability coefficient
    E_rec: float  # recursive entropy score
    D_conflict: float  # dependency conflict coefficient

    def stability_score(self) -> float:
        return (self.P_ETC * self.M_avail) / (self.E_rec + self.D_conflict)

    def classification(self) -> str:
        s = self.stability_score()
        if s >= 1.5:
            return "stable"
        if s >= 0.8:
            return "recoverable"
        return "unstable"
