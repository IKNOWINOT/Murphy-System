"""
RSC Client Adapter — Live wiring for the Recursive Stability Controller.

Provides an adapter that wraps the in-process ``RecursiveStabilityController``
(or an HTTP client pointing at port 8061) so it conforms to the interface
expected by :class:`StabilityIntegration._query_rsc`.

The adapter exposes a single ``get_status()`` method that returns a dict
containing at least ``stability_score``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RSCClientAdapter:
    """Adapter wrapping the in-process RSC controller.

    Parameters
    ----------
    controller : RecursiveStabilityController, optional
        A live ``RecursiveStabilityController`` instance.  When provided the
        adapter calls ``get_status()`` directly on the controller.
    http_base_url : str, optional
        Base URL (e.g. ``http://localhost:8061``) for an external RSC service.
        Used only when *controller* is ``None``.
    """

    def __init__(
        self,
        *,
        controller: Optional[Any] = None,
        http_base_url: Optional[str] = None,
    ) -> None:
        self._controller = controller
        self._http_base_url = http_base_url
        self._last_status: Optional[Dict[str, Any]] = None

    def get_status(self) -> Dict[str, Any]:
        """Return RSC status dict with at least ``stability_score``."""
        if self._controller is not None:
            return self._get_status_from_controller()
        if self._http_base_url is not None:
            return self._get_status_from_http()

        # No backend — return conservative safe default
        return {"stability_score": 1.0, "source": "default"}

    # ── private ───────────────────────────────────────────────────

    def _get_status_from_controller(self) -> Dict[str, Any]:
        """Query the in-process controller directly."""
        try:
            status = self._controller.get_status()
            # If the controller doesn't expose stability_score directly,
            # run a control cycle to get a score.
            if "stability_score" not in status:
                try:
                    cycle = self._controller.run_control_cycle()
                    score_info = cycle.get("stability_score", {})
                    if isinstance(score_info, dict):
                        score = score_info.get("score", 1.0)
                    else:
                        score = float(score_info)
                    status["stability_score"] = score
                except Exception as exc:
                    logger.debug("RSC stability score parse failed: %s", exc)
                    status["stability_score"] = 1.0
            self._last_status = status
            return status
        except Exception as exc:
            logger.exception("RSC controller query failed: %s", exc)
            return {"stability_score": 1.0, "source": "fallback", "error": str(exc)}

    def _get_status_from_http(self) -> Dict[str, Any]:
        """Query the RSC REST API via HTTP."""
        try:
            import json
            import urllib.request

            url = f"{self._http_base_url}/status"
            req = urllib.request.Request(url, method="GET")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            # Ensure stability_score is present
            if "stability_score" not in data:
                data["stability_score"] = 1.0
            self._last_status = data
            return data
        except Exception as exc:
            logger.exception("RSC HTTP query failed: %s", exc)
            return {"stability_score": 1.0, "source": "fallback", "error": str(exc)}

    @property
    def last_status(self) -> Optional[Dict[str, Any]]:
        return self._last_status


def create_rsc_adapter(
    *,
    controller: Optional[Any] = None,
    http_base_url: Optional[str] = None,
    auto_discover: bool = True,
) -> RSCClientAdapter:
    """Factory function that creates the best available RSC adapter.

    Parameters
    ----------
    controller : object, optional
        Existing ``RecursiveStabilityController`` instance.
    http_base_url : str, optional
        RSC service URL (e.g. ``http://localhost:8061``).
    auto_discover : bool
        When ``True`` and neither *controller* nor *http_base_url* are given,
        attempt to import and instantiate the in-process controller.

    Returns
    -------
    RSCClientAdapter
    """
    if controller is not None:
        return RSCClientAdapter(controller=controller)

    if http_base_url is not None:
        return RSCClientAdapter(http_base_url=http_base_url)

    if auto_discover:
        try:
            from recursive_stability_controller.rsc_service import (
                RecursiveStabilityController,
            )
            ctrl = RecursiveStabilityController()
            logger.info("Auto-discovered in-process RSC controller.")
            return RSCClientAdapter(controller=ctrl)
        except ImportError:
            logger.info("RSC module not available — using default adapter.")
        except Exception as exc:
            logger.exception("Failed to auto-discover RSC — using default adapter: %s", exc)

    return RSCClientAdapter()
