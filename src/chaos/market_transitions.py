"""
Fiat → Crypto → Stock Exchange and Currency Transition Simulator.

Design Label: CHAOS-005 — Market Transition Simulator
Owner: Platform Engineering

Models the full arc of monetary system transitions with historically
calibrated anchors:
  GOLD→BRETTON_WOODS (1944)        — orderly, ~1 year
  BRETTON_WOODS→PETRODOLLAR (1971) — Nixon Shock, USD vol +300%
  PETRODOLLAR→MODERN_FIAT          — gradual ongoing dedollarisation
  BTC Genesis (2009→2021)          — cypherpunk experiment → $69k ATH
  LUNA Collapse (2022)             — $60B evaporated in 72 hours
  FTX Collapse (2022)              — contagion cascade

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import math
import random
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_EXAMPLES = 5000


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CurrencySystem(Enum):
    GOLD_STANDARD = "gold_standard"
    BRETTON_WOODS = "bretton_woods"
    PETRODOLLAR = "petrodollar"
    MODERN_FIAT = "modern_fiat"
    CBDC = "cbdc"
    CRYPTO_DOMINANT = "crypto_dominant"
    HYBRID_MIXED = "hybrid_mixed"
    POST_FIAT = "post_fiat"


class MarketStructure(Enum):
    OPEN_OUTCRY = "open_outcry"
    ELECTRONIC = "electronic"
    DECENTRALIZED_DEX = "decentralized_dex"
    AI_DRIVEN = "ai_driven"
    QUANTUM_CLEARED = "quantum_cleared"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TransitionScenario:
    transition_id: str
    from_system: CurrencySystem
    to_system: CurrencySystem
    trigger: str
    duration_years: float
    volatility_multiplier: float
    adoption_rate_curve: List[float]
    winners: List[str]
    losers: List[str]
    regulatory_response: Dict[str, Any]


# ---------------------------------------------------------------------------
# Historical calibrations
# ---------------------------------------------------------------------------

_HISTORICAL_TRANSITIONS: Dict[str, Dict[str, Any]] = {
    "GOLD_TO_BRETTON_WOODS": {
        "from": CurrencySystem.GOLD_STANDARD,
        "to": CurrencySystem.BRETTON_WOODS,
        "trigger": "bretton_woods_agreement_1944",
        "duration_years": 1.0,
        "volatility_multiplier": 1.1,  # orderly
        "winners": ["US_dollar", "central_banks", "IMF"],
        "losers": ["gold_miners", "gold_standard_advocates"],
        "description": "Orderly post-WWII monetary settlement",
    },
    "BRETTON_WOODS_TO_PETRODOLLAR": {
        "from": CurrencySystem.BRETTON_WOODS,
        "to": CurrencySystem.PETRODOLLAR,
        "trigger": "nixon_shock_1971",
        "duration_years": 2.0,
        "volatility_multiplier": 4.0,  # USD vol +300%
        "winners": ["oil_exporters", "OPEC", "Wall_Street"],
        "losers": ["gold_holders", "fixed_exchange_rate_economies", "Europe"],
        "description": "Nixon Shock — USD-gold peg severed, USD vol +300%",
    },
    "PETRODOLLAR_TO_MODERN_FIAT": {
        "from": CurrencySystem.PETRODOLLAR,
        "to": CurrencySystem.MODERN_FIAT,
        "trigger": "gradual_dedollarisation",
        "duration_years": 30.0,
        "volatility_multiplier": 1.3,
        "winners": ["BRICS", "CNY", "EUR", "commodities_in_non_USD"],
        "losers": ["USD_reserve_holders", "US_Treasury"],
        "description": "Ongoing gradual dedollarisation of global trade",
    },
    "BTC_GENESIS_TO_PEAK": {
        "from": CurrencySystem.MODERN_FIAT,
        "to": CurrencySystem.HYBRID_MIXED,
        "trigger": "satoshi_genesis_block_2009",
        "duration_years": 12.0,
        "volatility_multiplier": 20.0,
        "winners": ["early_btc_holders", "crypto_exchanges", "mining_hardware"],
        "losers": ["traditional_banks", "payment_processors", "gold"],
        "description": "Bitcoin from cypherpunk experiment to $69k ATH (2009-2021)",
    },
    "LUNA_COLLAPSE": {
        "from": CurrencySystem.CRYPTO_DOMINANT,
        "to": CurrencySystem.HYBRID_MIXED,
        "trigger": "UST_depeg_bank_run_2022",
        "duration_years": 0.02,   # 72 hours
        "volatility_multiplier": 1000.0,
        "winners": ["short_sellers", "USD_stablecoins", "traditional_regulators"],
        "losers": ["LUNA_holders", "UST_holders", "DeFi_protocols", "Terraform_Labs"],
        "description": "$60B evaporated in 72 hours — algorithmic stablecoin failure",
    },
    "FTX_COLLAPSE": {
        "from": CurrencySystem.CRYPTO_DOMINANT,
        "to": CurrencySystem.HYBRID_MIXED,
        "trigger": "ftx_insolvency_2022",
        "duration_years": 0.08,   # ~1 month contagion
        "volatility_multiplier": 8.0,
        "winners": ["Binance_temporarily", "SEC_enforcement", "traditional_finance"],
        "losers": ["FTT_holders", "crypto_lenders", "retail_traders", "BlockFi", "Celsius"],
        "description": "FTX collapse — $8B shortfall, exchange contagion cascade",
    },
}

# Volatility profiles for transition pairs
_TRANSITION_VOLATILITY: Dict[tuple, float] = {
    (CurrencySystem.GOLD_STANDARD, CurrencySystem.BRETTON_WOODS): 1.1,
    (CurrencySystem.BRETTON_WOODS, CurrencySystem.PETRODOLLAR): 4.0,
    (CurrencySystem.PETRODOLLAR, CurrencySystem.MODERN_FIAT): 1.3,
    (CurrencySystem.MODERN_FIAT, CurrencySystem.CBDC): 1.8,
    (CurrencySystem.MODERN_FIAT, CurrencySystem.CRYPTO_DOMINANT): 15.0,
    (CurrencySystem.MODERN_FIAT, CurrencySystem.HYBRID_MIXED): 3.5,
    (CurrencySystem.CRYPTO_DOMINANT, CurrencySystem.HYBRID_MIXED): 8.0,
    (CurrencySystem.HYBRID_MIXED, CurrencySystem.POST_FIAT): 5.0,
}


# ---------------------------------------------------------------------------
# FiatCryptoTransitionSimulator — CHAOS-005
# ---------------------------------------------------------------------------

class FiatCryptoTransitionSimulator:
    """CHAOS-005 — Market Transition Simulator.

    Simulates transitions between monetary systems, crypto market events,
    and dedollarisation scenarios.
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)
        self._lock = threading.RLock()  # RLock: generate_training_examples calls simulate_transition
        self._example_cache: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def simulate_transition(
        self,
        from_system: CurrencySystem,
        to_system: CurrencySystem,
        trigger: Optional[str] = None,
        speed: str = "gradual",
    ) -> TransitionScenario:
        """Simulate a monetary system transition, returning a TransitionScenario."""
        with self._lock:
            vol_mult = self._calculate_exchange_rate_volatility(from_system, to_system)
            if speed == "shock":
                vol_mult *= self._rng.uniform(2.0, 5.0)
            elif speed == "rapid":
                vol_mult *= self._rng.uniform(1.3, 2.0)

            base_duration = _transition_duration(from_system, to_system, speed, self._rng)
            adoption_curve = self._model_adoption_s_curve(base_duration)

            winners, losers = _derive_winners_losers(from_system, to_system)
            regulatory = _model_regulatory_response_transition(from_system, to_system, vol_mult)

            scenario = TransitionScenario(
                transition_id=str(uuid.uuid4()),
                from_system=from_system,
                to_system=to_system,
                trigger=trigger or f"market_driven_{from_system.value}_to_{to_system.value}",
                duration_years=base_duration,
                volatility_multiplier=round(vol_mult, 3),
                adoption_rate_curve=adoption_curve,
                winners=winners,
                losers=losers,
                regulatory_response=regulatory,
            )
            logger.debug("Transition %s→%s vol=%.2fx", from_system.value, to_system.value, vol_mult)
            return scenario

    def simulate_crypto_market_event(self, event_type: str, magnitude: float) -> Dict[str, Any]:
        """Simulate a crypto market event (rug pull, exchange collapse, etc.)."""
        with self._lock:
            event_profiles = {
                "exchange_collapse": {"liquidity_drain": 0.85, "contagion_exchanges": 0.4, "vol_spike": 5.0},
                "stablecoin_depeg": {"liquidity_drain": 0.70, "contagion_exchanges": 0.6, "vol_spike": 8.0},
                "rug_pull": {"liquidity_drain": 1.0, "contagion_exchanges": 0.1, "vol_spike": 15.0},
                "regulatory_ban": {"liquidity_drain": 0.30, "contagion_exchanges": 0.2, "vol_spike": 3.0},
                "protocol_hack": {"liquidity_drain": 0.60, "contagion_exchanges": 0.3, "vol_spike": 6.0},
                "whale_dump": {"liquidity_drain": 0.20, "contagion_exchanges": 0.15, "vol_spike": 2.5},
            }
            profile = event_profiles.get(event_type, {"liquidity_drain": 0.3, "contagion_exchanges": 0.2, "vol_spike": 3.0})

            noise = self._rng.uniform(0.8, 1.3)
            return {
                "event_type": event_type,
                "magnitude": magnitude,
                "btc_price_impact_pct": round(-profile["vol_spike"] * magnitude * noise * 5.0, 2),
                "total_market_cap_loss_pct": round(profile["liquidity_drain"] * magnitude * 100 * noise, 2),
                "contagion_exchanges_pct": round(profile["contagion_exchanges"] * 100, 1),
                "vol_multiplier": round(profile["vol_spike"] * magnitude, 2),
                "recovery_days": int(30 * magnitude * self._rng.uniform(0.5, 3.0)),
            }

    def simulate_dedollarization(self, pct_of_trade: float = 0.1) -> Dict[str, Any]:
        """Model the impact of shifting pct_of_trade away from USD settlement."""
        with self._lock:
            # USD demand reduction → downward pressure on USD
            usd_demand_shock_pct = -(pct_of_trade * 0.6 * self._rng.uniform(0.8, 1.3))
            treasury_yield_impact = pct_of_trade * 0.5 * self._rng.uniform(0.4, 1.0)
            inflation_impact = pct_of_trade * 0.8 * self._rng.uniform(0.3, 1.2)

            beneficiaries = []
            if pct_of_trade > 0.05:
                beneficiaries.append("CNY")
            if pct_of_trade > 0.10:
                beneficiaries.extend(["gold", "EUR"])
            if pct_of_trade > 0.20:
                beneficiaries.extend(["BRICS_basket", "SDR"])

            return {
                "pct_of_global_trade_non_usd": round(pct_of_trade * 100, 1),
                "usd_demand_reduction_pct": round(usd_demand_shock_pct * 100, 2),
                "us_treasury_yield_increase_bps": round(treasury_yield_impact * 100, 1),
                "us_inflation_increase_pct": round(inflation_impact, 2),
                "dollar_index_dxy_impact": round(usd_demand_shock_pct * 15, 2),
                "beneficiary_currencies": beneficiaries,
                "transition_years": max(1, int(pct_of_trade * 30)),
                "geopolitical_risk_score": round(min(10.0, pct_of_trade * 20), 1),
            }

    def generate_training_examples(self, num_scenarios: int = 75) -> List[Dict[str, Any]]:
        """Generate ML training data from random transition simulations."""
        with self._lock:
            examples: List[Dict[str, Any]] = []
            systems = list(CurrencySystem)
            speeds = ["gradual", "rapid", "shock"]

            for _ in range(num_scenarios):
                from_sys = self._rng.choice(systems)
                to_sys = self._rng.choice([s for s in systems if s != from_sys])
                speed = self._rng.choice(speeds)

                scenario = self.simulate_transition(from_sys, to_sys, speed=speed)

                example: Dict[str, Any] = {
                    "input": {
                        "from_system": from_sys.value,
                        "to_system": to_sys.value,
                        "speed": speed,
                        "num_winners": len(scenario.winners),
                        "num_losers": len(scenario.losers),
                    },
                    "output": {
                        "volatility_multiplier": scenario.volatility_multiplier,
                        "duration_years": scenario.duration_years,
                        "final_adoption_pct": scenario.adoption_rate_curve[-1] if scenario.adoption_rate_curve else 1.0,
                    },
                    "adoption_curve": scenario.adoption_rate_curve,
                    "source": "FiatCryptoTransitionSimulator-CHAOS-005",
                }
                if len(self._example_cache) < _MAX_EXAMPLES:
                    self._example_cache.append(example)
                examples.append(example)

            return examples

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _model_adoption_s_curve(
        self, duration_years: float, early_adopter_pct: float = 0.05
    ) -> List[float]:
        """Return a normalised S-curve adoption list (annual snapshots, 0-1)."""
        years = max(1, int(duration_years))
        curve: List[float] = []
        midpoint = years * 0.5
        steepness = 6.0 / max(1, years)  # steeper curve for shorter transitions
        for t in range(1, years + 1):
            val = 1.0 / (1.0 + math.exp(-steepness * (t - midpoint)))
            val = early_adopter_pct + (1.0 - early_adopter_pct) * val
            curve.append(round(val, 4))
        return curve

    def _calculate_exchange_rate_volatility(
        self, from_system: CurrencySystem, to_system: CurrencySystem
    ) -> float:
        """Return volatility multiplier for the given system transition pair."""
        key = (from_system, to_system)
        base = _TRANSITION_VOLATILITY.get(key, _TRANSITION_VOLATILITY.get((to_system, from_system), 2.0))
        return base * self._rng.uniform(0.8, 1.3)


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------

def _transition_duration(
    from_sys: CurrencySystem, to_sys: CurrencySystem, speed: str, rng: random.Random
) -> float:
    base_years = {
        "shock": 0.25,
        "rapid": 2.0,
        "gradual": 15.0,
    }.get(speed, 10.0)

    if to_sys in (CurrencySystem.POST_FIAT, CurrencySystem.CRYPTO_DOMINANT):
        base_years *= rng.uniform(0.5, 2.0)
    return round(base_years * rng.uniform(0.7, 1.4), 2)


def _derive_winners_losers(
    from_sys: CurrencySystem, to_sys: CurrencySystem
) -> tuple[List[str], List[str]]:
    all_winners = {
        CurrencySystem.CBDC: ["central_banks", "governments", "surveillance_tech"],
        CurrencySystem.CRYPTO_DOMINANT: ["miners", "early_holders", "DeFi_protocols", "crypto_exchanges"],
        CurrencySystem.HYBRID_MIXED: ["multi_asset_funds", "fintech", "stablecoin_issuers"],
        CurrencySystem.POST_FIAT: ["AI_agents", "tokenized_assets", "programmable_money"],
    }
    all_losers = {
        CurrencySystem.GOLD_STANDARD: ["commercial_banks", "fiat_currency_holders"],
        CurrencySystem.MODERN_FIAT: ["cash_heavy_businesses", "traditional_payment_rails"],
        CurrencySystem.PETRODOLLAR: ["oil_importers_in_USD", "forex_reserve_managers"],
    }
    return (
        all_winners.get(to_sys, ["early_movers", "adaptable_institutions"]),
        all_losers.get(from_sys, ["legacy_incumbents", "late_adopters"]),
    )


def _model_regulatory_response_transition(
    from_sys: CurrencySystem, to_sys: CurrencySystem, vol_mult: float
) -> Dict[str, Any]:
    if vol_mult > 10.0:
        return {"action": "emergency_intervention", "severity": "critical",
                "tools": ["capital_controls", "circuit_breakers", "emergency_legislation"]}
    if vol_mult > 4.0:
        return {"action": "coordinated_central_bank_response", "severity": "high",
                "tools": ["fx_intervention", "rate_hikes", "macroprudential_limits"]}
    if vol_mult > 2.0:
        return {"action": "enhanced_monitoring", "severity": "medium",
                "tools": ["stress_tests", "disclosure_requirements"]}
    return {"action": "standard_oversight", "severity": "low",
            "tools": ["periodic_review", "guidance_updates"]}
