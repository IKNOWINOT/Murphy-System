# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
API Capability Builder for Murphy System Runtime

Detects when an artifact or workflow references live external data domains
(banking, email validation, stock prices, currency exchange, fuel/material
costs, etc.) and automatically:

  1. Identifies which APIs are needed via the ExternalApiSensor.
  2. Auto-generates a capability stub (scaffold) for each missing API — as
     far as possible without requiring HITL review.
  3. Raises a ticket in the TicketingAdapter (type API_BUILD) that requires
     OWNER-level (founder/admin) approval before full wiring proceeds.
  4. Records all findings and actions in the Librarian knowledge layers.

Permission gate
---------------
TRIGGER_API_BUILD is granted only to Role.OWNER (founder-admin level).
Any request arriving without that permission is rejected with a clear
message — the ticket is created but marked "pending_approval" and no
scaffold is generated.

Architecture
------------

  ExternalApiSensor (world-model calibration sensor)
      Reads artifact content and detects data-domain keywords.
      Returns a SensorReading (ok / warn / alert) plus a structured
      list of ApiNeed objects as reading metadata.

  ApiCapabilityBuilder
      Takes a list of ApiNeed objects and, for each:
        a) Checks whether a stub already exists in src/api_capabilities/.
        b) If not, writes a minimal Python stub module (no HITL needed
           for the scaffold; HITL is only required if the stub needs to
           actually call a live production endpoint).
        c) Calls TicketingAdapter.request_api_build() with the stub path
           and auto_scaffold=True.
        d) Writes a Librarian knowledge entry.

  WingmanApiGapChecker
      Top-level helper used by WingmanSystem.check_api_needs().
      Combines sensor + builder + RBAC gate.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# API Domain Catalog
# ---------------------------------------------------------------------------
# Each entry defines an external data domain that Murphy System may need.
# "keywords" are matched case-insensitively against artifact text.
# "sensor_status" is the reading severity when the domain is detected but
# no API capability exists yet.

_API_DOMAIN_CATALOG: List[Dict[str, Any]] = [
    {
        "category": "banking",
        "keywords": ["bank account", "bank data", "iban", "sort code", "routing number",
                     "bank balance", "open banking", "plaid", "yodlee", "fintech"],
        "api_name": "Open Banking / Plaid API",
        "provider": "Plaid",
        "env_var": "PLAID_CLIENT_ID",
        "description": "Bank account data, transactions, and balance verification.",
        "docs_url": "https://plaid.com/docs/",
    },
    {
        "category": "email_validation",
        "keywords": ["email validation", "validate email", "email deliverability",
                     "mx record", "disposable email", "email verify"],
        "api_name": "Email Validation API",
        "provider": "ZeroBounce / Hunter.io",
        "env_var": "ZEROBOUNCE_API_KEY",
        "description": "Real-time email address validation and deliverability check.",
        "docs_url": "https://www.zerobounce.net/docs/",
    },
    {
        "category": "stock",
        "keywords": ["stock price", "stock ticker", "equity price", "nasdaq", "nyse",
                     "market cap", "share price", "alpha vantage", "polygon.io"],
        "api_name": "Stock Market Data API",
        "provider": "Alpha Vantage / Polygon.io",
        "env_var": "ALPHA_VANTAGE_API_KEY",
        "description": "Real-time and historical equity price data.",
        "docs_url": "https://www.alphavantage.co/documentation/",
    },
    {
        "category": "currency",
        "keywords": ["exchange rate", "currency conversion", "forex", "fx rate",
                     "usd to", "eur to", "gbp to", "currency value", "spot rate"],
        "api_name": "Currency Exchange Rate API",
        "provider": "Open Exchange Rates / Fixer.io",
        "env_var": "OPEN_EXCHANGE_RATES_APP_ID",
        "description": "Live and historical foreign exchange rates.",
        "docs_url": "https://openexchangerates.org/documentation",
    },
    {
        "category": "fuel_costs",
        "keywords": ["fuel price", "fuel cost", "petrol price", "diesel price",
                     "gas price", "energy price", "cost of fuel", "barrel price",
                     "brent crude", "wti crude"],
        "api_name": "Fuel / Energy Price API",
        "provider": "EIA / Quandl",
        "env_var": "EIA_API_KEY",
        "description": "Fuel, crude oil, and energy commodity price data.",
        "docs_url": "https://www.eia.gov/opendata/",
    },
    {
        "category": "material_costs",
        "keywords": ["material cost", "commodity price", "steel price", "copper price",
                     "lumber price", "raw material", "cost of materials", "bulk price"],
        "api_name": "Commodity / Material Price API",
        "provider": "World Bank Commodities / Quandl",
        "env_var": "QUANDL_API_KEY",
        "description": "Commodity and raw material price data.",
        "docs_url": "https://www.quandl.com/tools/api",
    },
    {
        "category": "credit_scoring",
        "keywords": ["credit score", "credit check", "credit rating", "creditworthiness",
                     "equifax", "experian", "transunion", "fico score"],
        "api_name": "Credit Scoring / Bureau API",
        "provider": "Experian / Equifax",
        "env_var": "EXPERIAN_API_KEY",
        "description": "Credit bureau data for risk scoring and identity checks.",
        "docs_url": "https://developer.experian.com/",
    },
    {
        "category": "tax_rates",
        "keywords": ["tax rate", "vat rate", "sales tax", "gst", "tax calculation",
                     "tax compliance", "avalara", "taxjar"],
        "api_name": "Tax Rate / Compliance API",
        "provider": "Avalara / TaxJar",
        "env_var": "AVALARA_LICENSE_KEY",
        "description": "Real-time tax rate calculation and filing compliance.",
        "docs_url": "https://developer.avalara.com/",
    },
]

# ---------------------------------------------------------------------------
# ApiNeed — structured description of a detected API requirement
# ---------------------------------------------------------------------------

@dataclass
class ApiNeed:
    """A single detected external API requirement."""
    category: str
    api_name: str
    provider: str
    env_var: str
    description: str
    docs_url: str
    detected_keywords: List[str] = field(default_factory=list)
    stub_path: Optional[str] = None      # set after scaffold is generated
    ticket_id: Optional[str] = None      # set after ticket is created
    scaffold_status: str = "pending"     # "pending" | "generated" | "exists"


# ---------------------------------------------------------------------------
# ExternalApiSensor (world-model calibration sensor)
# ---------------------------------------------------------------------------

class ExternalApiSensor:
    """Detects live data domain references in artifact content.

    Produces a SensorReading (from wingman_system) plus a list of ApiNeed
    objects in the reading metadata.

    Integrated into the WorldModelCalibrator as a custom sensor.
    """

    SENSOR_ID = "external_api"

    def read(self, artifact: Dict[str, Any]) -> Any:
        """Scan artifact content for external data domain keywords.

        Returns a SensorReading with:
          status "ok"    — no external data domains detected
          status "warn"  — at least one external data domain detected (needs API)
          value          — fraction of catalog domains NOT detected (1.0 = none needed)
          metadata       — list of ApiNeed objects (attached as .api_needs attribute)
        """
        # Import here to keep this module importable even if wingman_system is not yet loaded
        from src.wingman_system import SensorReading, SensorStatus  # noqa: PLC0415

        content = str(artifact.get("content") or artifact.get("result") or "").lower()
        needs: List[ApiNeed] = []
        seen_categories: set = set()

        for entry in _API_DOMAIN_CATALOG:
            category = entry["category"]
            if category in seen_categories:
                continue
            matched = [kw for kw in entry["keywords"] if kw.lower() in content]
            if matched:
                seen_categories.add(category)
                needs.append(ApiNeed(
                    category=category,
                    api_name=entry["api_name"],
                    provider=entry["provider"],
                    env_var=entry["env_var"],
                    description=entry["description"],
                    docs_url=entry["docs_url"],
                    detected_keywords=matched,
                ))

        if not needs:
            reading = SensorReading(
                sensor_id=self.SENSOR_ID,
                dimension="external_api",
                value=1.0,
                status=SensorStatus.OK,
                detail="No external data domain references detected.",
            )
        else:
            categories = ", ".join(n.category for n in needs)
            reading = SensorReading(
                sensor_id=self.SENSOR_ID,
                dimension="external_api",
                value=round(1.0 - len(needs) / len(_API_DOMAIN_CATALOG), 2),
                status=SensorStatus.WARN,
                detail=(
                    f"{len(needs)} external data domain(s) detected that may require "
                    f"API capabilities: {categories}. "
                    f"Tickets will be raised for missing integrations."
                ),
            )

        # Attach api_needs as an attribute so callers can retrieve them
        reading.api_needs = needs  # type: ignore[attr-defined]
        return reading

    @staticmethod
    def scan_text(text: str) -> List[ApiNeed]:
        """Convenience method — scan raw text and return ApiNeed list."""
        sensor = ExternalApiSensor()
        reading = sensor.read({"content": text})
        return getattr(reading, "api_needs", [])


# ---------------------------------------------------------------------------
# Scaffold generator
# ---------------------------------------------------------------------------

_STUB_TEMPLATE = '''\
# Copyright © 2020 Inoni LLC — Auto-generated by Murphy System ApiCapabilityBuilder
# Category : {category}
# API Name : {api_name}
# Provider : {provider}
# Env Var  : {env_var}
# Docs     : {docs_url}
# Status   : STUB — requires OWNER approval and API key before going live
"""
{api_name} capability stub.

This file was auto-generated by the Murphy System ApiCapabilityBuilder
after a Wingman validation sensor detected that an artifact references
'{category}' data without a corresponding API capability.

TO ACTIVATE:
  1. Obtain an API key from {provider} ({docs_url})
  2. Set {env_var}=<your-key> in your .env file
  3. Implement the functions below (replace raise NotImplementedError)
  4. Approve the corresponding API_BUILD ticket in Murphy System
"""
from __future__ import annotations
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_API_KEY = os.environ.get("{env_var}", "")


def is_available() -> bool:
    """Return True if the API key is configured."""
    return bool(_API_KEY)


def get_status() -> Dict[str, Any]:
    """Return capability status."""
    return {{
        "api": "{api_name}",
        "provider": "{provider}",
        "env_var": "{env_var}",
        "configured": is_available(),
        "status": "active" if is_available() else "stub_awaiting_key",
    }}


def fetch(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fetch data from {api_name}.

    Raises NotImplementedError until the stub is implemented.
    Set {env_var} to activate.
    """
    if not is_available():
        raise RuntimeError(
            f"{{'{env_var}'}} is not set. Obtain a key from {provider} and set "
            f"the environment variable before calling this function."
        )
    raise NotImplementedError(
        "Auto-generated stub — implement fetch() body after obtaining API credentials."
    )
'''


def _write_stub(
    capabilities_dir: str,
    need: ApiNeed,
) -> Tuple[str, bool]:
    """Write a capability stub file.

    Returns (stub_path, was_newly_created).
    """
    slug = re.sub(r"[^a-z0-9]+", "_", need.category.lower()).strip("_")
    filename = f"{slug}_api.py"
    stub_path = os.path.join(capabilities_dir, filename)

    if os.path.exists(stub_path):
        return stub_path, False

    content = _STUB_TEMPLATE.format(
        category=need.category,
        api_name=need.api_name,
        provider=need.provider,
        env_var=need.env_var,
        docs_url=need.docs_url,
    )
    try:
        os.makedirs(capabilities_dir, exist_ok=True)
        with open(stub_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        logger.info("ApiCapabilityBuilder: wrote stub %s", stub_path)
        return stub_path, True
    except OSError as exc:
        logger.warning("ApiCapabilityBuilder: could not write stub %s: %s", stub_path, exc)
        return stub_path, False


# ---------------------------------------------------------------------------
# ApiCapabilityBuilder
# ---------------------------------------------------------------------------

class ApiCapabilityBuilder:
    """Auto-scaffolds API capability stubs and raises tickets for missing APIs.

    Usage
    -----
    builder = ApiCapabilityBuilder(ticketing_adapter=ta, librarian=lib)
    results = builder.process_needs(needs, requester="system", owner_authorized=True)

    Parameters
    ----------
    ticketing_adapter : TicketingAdapter instance (or None for testing)
    librarian         : SystemLibrarian instance (or None)
    capabilities_dir  : directory where stubs are written (default: src/api_capabilities)
    """

    def __init__(
        self,
        ticketing_adapter: Optional[Any] = None,
        librarian: Optional[Any] = None,
        capabilities_dir: Optional[str] = None,
    ) -> None:
        self._ticketing = ticketing_adapter
        self._librarian = librarian
        self._lock = threading.Lock()
        self._processed: List[ApiNeed] = []
        # Default to src/api_capabilities/ relative to this file's location
        if capabilities_dir is None:
            _here = os.path.dirname(os.path.abspath(__file__))
            capabilities_dir = os.path.join(_here, "api_capabilities")
        self._capabilities_dir = capabilities_dir

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process_needs(
        self,
        needs: List[ApiNeed],
        requester: str = "murphy_wingman",
        owner_authorized: bool = False,
    ) -> List[ApiNeed]:
        """Process a list of ApiNeed objects.

        For each need:
          1. If owner_authorized: write a scaffold stub (no HITL).
          2. Raise an API_BUILD ticket regardless of authorization.
          3. Write a Librarian knowledge entry.

        Returns the updated list of ApiNeed objects with stub_path and
        ticket_id populated.
        """
        updated: List[ApiNeed] = []
        for need in needs:
            result = self._process_one(need, requester, owner_authorized)
            updated.append(result)

        with self._lock:
            self._processed.extend(updated)

        return updated

    def _process_one(
        self,
        need: ApiNeed,
        requester: str,
        owner_authorized: bool,
    ) -> ApiNeed:
        """Process a single ApiNeed: scaffold + ticket + librarian."""
        # Step 1: scaffold (only if OWNER authorized)
        if owner_authorized:
            stub_path, newly_created = _write_stub(self._capabilities_dir, need)
            need.stub_path = stub_path
            need.scaffold_status = "generated" if newly_created else "exists"
        else:
            need.scaffold_status = "pending"

        # Step 2: raise ticket
        if self._ticketing is not None:
            try:
                from src.ticketing_adapter import TicketType  # noqa: PLC0415
                ticket = self._ticketing.request_api_build(
                    api_name=need.api_name,
                    category=need.category,
                    requester=requester,
                    description=(
                        f"Detected keywords: {', '.join(need.detected_keywords[:5])}. "
                        f"Stub path: {need.stub_path or 'not yet generated'}. "
                        f"Docs: {need.docs_url}"
                    ),
                    env_var=need.env_var,
                    provider=need.provider,
                    auto_scaffold=(need.scaffold_status in ("generated", "exists")),
                )
                need.ticket_id = ticket.ticket_id
                logger.info(
                    "ApiCapabilityBuilder: ticket %s for %s (scaffold=%s)",
                    ticket.ticket_id, need.api_name, need.scaffold_status,
                )
            except Exception as exc:
                logger.warning("ApiCapabilityBuilder: ticket creation failed: %s", exc)

        # Step 3: librarian
        self._write_librarian_entry(need, owner_authorized)

        return need

    def _write_librarian_entry(self, need: ApiNeed, owner_authorized: bool) -> None:
        """Record API need in Librarian knowledge layers."""
        if not self._librarian:
            return
        try:
            action = "scaffold generated" if need.scaffold_status == "generated" else (
                "stub exists" if need.scaffold_status == "exists" else "pending owner approval"
            )
            self._librarian.add_knowledge_entry({
                "category": "api_capability",
                "topic": f"API Need Detected: {need.api_name} ({need.category})",
                "description": (
                    f"WingmanSystem detected that an artifact references '{need.category}' "
                    f"live data. Required API: {need.api_name} (provider: {need.provider}). "
                    f"Env var: {need.env_var}. "
                    f"Action taken: {action}. "
                    f"Ticket: {need.ticket_id or 'not created'}. "
                    f"Docs: {need.docs_url}."
                ),
                "related_modules": ["api_capability_builder", f"api_capabilities.{need.category}_api"],
                "related_functions": ["process_needs", "fetch", "get_status"],
                "references": [
                    f"ticket:{need.ticket_id or 'pending'}",
                    f"env_var:{need.env_var}",
                    f"docs:{need.docs_url}",
                ],
            })
        except Exception as exc:
            logger.debug("Librarian write skipped for %s: %s", need.api_name, exc)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            processed = list(self._processed)
        return {
            "total_needs_processed": len(processed),
            "scaffolds_generated": sum(1 for n in processed if n.scaffold_status == "generated"),
            "scaffolds_existing": sum(1 for n in processed if n.scaffold_status == "exists"),
            "pending_owner_approval": sum(1 for n in processed if n.scaffold_status == "pending"),
            "tickets_raised": sum(1 for n in processed if n.ticket_id),
            "categories": list({n.category for n in processed}),
        }


# ---------------------------------------------------------------------------
# WingmanApiGapChecker — combines sensor + RBAC gate + builder
# ---------------------------------------------------------------------------

class WingmanApiGapChecker:
    """Top-level helper used by WingmanSystem.check_api_needs().

    Checks whether the caller has OWNER-level permission (TRIGGER_API_BUILD),
    runs the ExternalApiSensor, and hands off to the ApiCapabilityBuilder.
    """

    def __init__(
        self,
        ticketing_adapter: Optional[Any] = None,
        librarian: Optional[Any] = None,
        rbac_governance: Optional[Any] = None,
        capabilities_dir: Optional[str] = None,
    ) -> None:
        self._sensor = ExternalApiSensor()
        self._builder = ApiCapabilityBuilder(
            ticketing_adapter=ticketing_adapter,
            librarian=librarian,
            capabilities_dir=capabilities_dir,
        )
        self._rbac = rbac_governance

    def check(
        self,
        artifact: Dict[str, Any],
        requester: str = "murphy_wingman",
        owner_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Scan artifact, check OWNER permission, scaffold + ticket missing APIs.

        Returns a dict with:
          api_needs_detected   — list of detected ApiNeed dicts
          owner_authorized     — whether TRIGGER_API_BUILD was granted
          scaffolds_generated  — count of newly written stubs
          tickets_raised       — list of ticket IDs created
          auth_message         — human-readable auth decision
        """
        # Step 1: Sensor scan
        reading = self._sensor.read(artifact)
        needs: List[ApiNeed] = getattr(reading, "api_needs", [])

        if not needs:
            return {
                "api_needs_detected": [],
                "owner_authorized": False,
                "scaffolds_generated": 0,
                "tickets_raised": [],
                "auth_message": "No external API needs detected.",
            }

        # Step 2: RBAC gate — TRIGGER_API_BUILD is OWNER-only
        owner_authorized = self._check_owner_permission(owner_user_id)
        auth_message = (
            "OWNER permission granted — scaffolds will be auto-generated."
            if owner_authorized
            else (
                "TRIGGER_API_BUILD requires OWNER (founder-admin) role. "
                "Tickets will be raised but scaffolds will not be generated "
                "until an OWNER approves via POST /api/wingman/api-gaps/build."
            )
        )

        # Step 3: Build — tickets always raised; stubs only if owner_authorized
        processed = self._builder.process_needs(
            needs,
            requester=requester,
            owner_authorized=owner_authorized,
        )

        return {
            "api_needs_detected": [self._need_to_dict(n) for n in processed],
            "owner_authorized": owner_authorized,
            "scaffolds_generated": sum(1 for n in processed if n.scaffold_status == "generated"),
            "tickets_raised": [n.ticket_id for n in processed if n.ticket_id],
            "auth_message": auth_message,
            "sensor_detail": reading.detail,
        }

    def _check_owner_permission(self, user_id: Optional[str]) -> bool:
        """Return True if user_id holds TRIGGER_API_BUILD permission."""
        if not user_id:
            return False
        if self._rbac is None:
            # No RBAC configured — deny by default (safe fail-closed)
            return False
        try:
            from src.rbac_governance import Permission  # noqa: PLC0415
            allowed, _ = self._rbac.check_permission(user_id, Permission.TRIGGER_API_BUILD)
            return allowed
        except Exception as exc:
            logger.debug("RBAC check failed: %s", exc)
            return False

    @staticmethod
    def _need_to_dict(need: ApiNeed) -> Dict[str, Any]:
        return {
            "category": need.category,
            "api_name": need.api_name,
            "provider": need.provider,
            "env_var": need.env_var,
            "description": need.description,
            "docs_url": need.docs_url,
            "detected_keywords": need.detected_keywords,
            "stub_path": need.stub_path,
            "ticket_id": need.ticket_id,
            "scaffold_status": need.scaffold_status,
        }
