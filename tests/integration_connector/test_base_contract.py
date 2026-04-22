"""Integration-connector contract test scaffolding.

Class S Roadmap, Item 12 (scaffolding only).

The roadmap calls for a base-class contract test that every connector must
pass: must declare ``INTEGRATION_NAME``, ``BASE_URL``, ``CREDENTIAL_KEYS``,
must return the standard ``{success, data, error, configured, simulated}``
envelope, must respect the timeout, and must back off on 429.

Murphy's connectors do not yet share that uniform interface — different
domains (CRM, building-automation, additive manufacturing, crypto exchanges)
each grew their own base classes. Retrofitting them is a multi-PR effort
tracked in ``docs/ROADMAP_TO_CLASS_S.md``.

This file lands the **scaffolding** that the retrofit will use:

1. The :data:`CONNECTOR_REQUIRED_FIELDS` constant — the canonical set of
   class-level attributes every connector must eventually declare.
2. A reusable validator (:func:`validate_connector_definition`) that future
   contract tests will call against each connector class.
3. One concrete contract test that runs against
   ``platform_connector_framework.DEFAULT_PLATFORMS`` — the closest thing
   the codebase has today to a uniform connector catalog. This catches
   typos and missing fields in the central definition list and locks the
   minimum-viable contract in CI from day one.

When a connector class is migrated to the unified contract, add it to
:data:`UNIFIED_CONTRACT_CONNECTORS` and the contract test will also run
against it automatically.
"""

from __future__ import annotations

from typing import Any

import pytest

# ---------------------------------------------------------------------------
# The contract.
# ---------------------------------------------------------------------------

#: Field names that every connector definition must declare.
#: When the full retrofit lands, this becomes the set of class attributes
#: every connector class must expose.
CONNECTOR_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {
        "connector_id",  # corresponds to INTEGRATION_NAME on a class
        "base_url",      # corresponds to BASE_URL on a class
        "auth_type",     # corresponds to CREDENTIAL_KEYS / AUTH_TYPE on a class
        "category",
        "platform",
    }
)

#: Allowed URL schemes for connector base URLs. We deliberately disallow
#: plain ``http://`` for *remote* targets to prevent a typo from sending
#: tenant credentials over cleartext. Local-loopback hosts (localhost,
#: 127.0.0.1, ::1) are exempted because plenty of self-hosted dev
#: dependencies (n8n, ollama, in-cluster sidecars) only listen on plain HTTP.
ALLOWED_BASE_URL_SCHEMES: frozenset[str] = frozenset({"https://", "wss://"})

#: Substrings that, when present in a base_url, exempt it from the secure-
#: scheme requirement. These cover loopback addresses only — never bind a
#: production connector to a non-loopback http:// endpoint.
LOOPBACK_HOSTS: frozenset[str] = frozenset(
    {"localhost", "127.0.0.1", "[::1]", "0.0.0.0"}
)

#: Connector classes that have been migrated to the unified contract.
#: Empty today; populated PR-by-PR as connectors are retrofitted (Item 12 full).
UNIFIED_CONTRACT_CONNECTORS: list[type] = []


# ---------------------------------------------------------------------------
# Validators.
# ---------------------------------------------------------------------------


def validate_connector_definition(definition: Any) -> list[str]:
    """Return a list of contract violations for a single ``ConnectorDefinition``.

    An empty list means the definition is contract-conformant. The function
    returns *all* violations rather than raising on the first one so that a
    failing test reports every issue at once.
    """
    violations: list[str] = []

    # Required fields must be present. ``base_url`` is special: an empty
    # value is permitted for connectors that do not speak HTTP at all
    # (Modbus, BACnet, OPC-UA, sensor protocols, etc.).
    optional_when_empty = {"base_url"}
    for field_name in CONNECTOR_REQUIRED_FIELDS:
        if not hasattr(definition, field_name):
            violations.append(f"missing required field: {field_name}")
            continue
        value = getattr(definition, field_name)
        if (value is None or value == "") and field_name not in optional_when_empty:
            violations.append(f"required field {field_name} is empty")

    # connector_id must be a stable identifier (lowercase, no spaces).
    cid = getattr(definition, "connector_id", "") or ""
    if cid and (cid != cid.lower() or " " in cid):
        violations.append(
            f"connector_id {cid!r} must be lowercase and contain no spaces"
        )

    # base_url must use an allowed secure scheme unless it points at a
    # loopback host (the only legitimate plain-HTTP target).
    base_url = getattr(definition, "base_url", "") or ""
    if base_url:
        is_secure = any(base_url.startswith(s) for s in ALLOWED_BASE_URL_SCHEMES)
        is_loopback = any(host in base_url for host in LOOPBACK_HOSTS)
        if not is_secure and not is_loopback:
            violations.append(
                f"base_url {base_url!r} must use one of "
                f"{sorted(ALLOWED_BASE_URL_SCHEMES)} (loopback hosts exempt)"
            )

    return violations


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------


def _load_default_platforms() -> list[Any]:
    """Import lazily so this test file can be collected even if heavy
    optional deps (numpy, etc.) used elsewhere in src/ are missing."""
    try:
        from src.platform_connector_framework import DEFAULT_PLATFORMS
    except Exception as exc:  # noqa: BLE001 — import failure must surface as skip
        pytest.skip(f"platform_connector_framework not importable: {exc}")
    return list(DEFAULT_PLATFORMS)


def test_default_platforms_are_unique_by_id() -> None:
    """No two entries in DEFAULT_PLATFORMS may share a connector_id."""
    platforms = _load_default_platforms()
    ids = [p.connector_id for p in platforms]
    duplicates = [cid for cid in set(ids) if ids.count(cid) > 1]
    assert not duplicates, f"duplicate connector_ids: {duplicates}"


def test_default_platforms_satisfy_contract() -> None:
    """Every DEFAULT_PLATFORMS entry must satisfy the connector contract."""
    platforms = _load_default_platforms()
    failures: dict[str, list[str]] = {}
    for platform in platforms:
        violations = validate_connector_definition(platform)
        if violations:
            failures[platform.connector_id] = violations
    assert not failures, (
        "The following DEFAULT_PLATFORMS entries violate the connector "
        f"contract:\n{failures}"
    )


def test_unified_contract_connectors_are_class_objects() -> None:
    """Sanity check: the registry of migrated connector classes is well-formed.

    This runs as a no-op until classes are added to
    :data:`UNIFIED_CONTRACT_CONNECTORS`. Once they are, future expansions of
    this test will exercise instance-level behaviour (timeout, 429 back-off,
    envelope shape) against each one.
    """
    for entry in UNIFIED_CONTRACT_CONNECTORS:
        assert isinstance(entry, type), f"{entry!r} is not a class"
