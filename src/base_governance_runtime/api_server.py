"""
Governance API Server Implementation

REST API for the base governance and compliance runtime.
Provides endpoints for preset management, validation, and compliance monitoring.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from .governance_runtime_complete import GovernanceRuntime, RuntimeConfig

logger = logging.getLogger(__name__)


class GovernanceAPI:
    """REST API for governance operations"""

    def __init__(self, runtime: GovernanceRuntime):
        self.runtime = runtime
        self.logger = logging.getLogger(__name__)

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        try:
            status = self.runtime.get_system_status()
            return {
                "success": True,
                "data": status
            }
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                "success": False,
                "error": str(exc)
            }

    def initialize_system(self) -> Dict[str, Any]:
        """Initialize the governance runtime"""
        try:
            validation_result = self.runtime.initialize()
            return {
                "success": True,
                "data": {
                    "validation_id": validation_result.validation_id,
                    "overall_status": validation_result.overall_status.value,
                    "compliance_percentage": validation_result.get_compliance_percentage(),
                    "total_gaps": len(validation_result.gaps),
                    "critical_gaps": len(validation_result.get_critical_gaps())
                }
            }
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                "success": False,
                "error": str(exc)
            }

    def activate_system(self) -> Dict[str, Any]:
        """Activate system with governance validation"""
        try:
            result = self.runtime.activate_system()
            return {
                "success": True,
                "data": result
            }
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                "success": False,
                "error": str(exc)
            }

    def get_validation_output(self) -> Dict[str, Any]:
        """Get complete validation output"""
        try:
            validation_output = self.runtime.get_validation_output()
            return {
                "success": True,
                "data": validation_output
            }
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                "success": False,
                "error": str(exc)
            }

    def list_presets(self) -> Dict[str, Any]:
        """List all available presets"""
        try:
            presets = self.runtime.preset_manager.list_presets()
            preset_data = []
            for preset in presets:
                preset_data.append({
                    "preset_id": preset.preset_id,
                    "name": preset.name,
                    "domain": preset.domain,
                    "version": preset.version,
                    "description": preset.description,
                    "jurisdiction": preset.jurisdiction,
                    "enabled": preset.preset_id in self.runtime.preset_manager.enabled_presets
                })

            return {
                "success": True,
                "data": preset_data
            }
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                "success": False,
                "error": str(exc)
            }

    def handle_preset_selection(self, preset_id: str) -> Dict[str, Any]:
        """Handle preset selection with gap analysis"""
        try:
            result = self.runtime.handle_preset_selection(preset_id)
            return {
                "success": True,
                "data": result
            }
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                "success": False,
                "error": str(exc)
            }
