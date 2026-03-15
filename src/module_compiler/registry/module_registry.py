"""
Module Registry

Stores and indexes compiled modules for discovery and retrieval.

Owner: INONI LLC / Corey Post (corey.gfc@gmail.com)
"""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models.module_spec import Capability, ModuleSpec

logger = logging.getLogger(__name__)


class ModuleRegistry:
    """
    Registry for compiled modules.

    Provides:
    - Module storage
    - Capability indexing
    - Search and discovery
    - Version management
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize module registry.

        Args:
            storage_path: Path to store module specs
        """
        if storage_path is None:
            storage_path = os.path.join(tempfile.gettempdir(), "module_registry")
        self.storage_path = storage_path
        self.modules_path = os.path.join(storage_path, "modules")
        self.index_path = os.path.join(storage_path, "index.json")

        # Create storage directories
        os.makedirs(self.modules_path, exist_ok=True)

        # Load or create index
        self.index = self._load_index()

    def register(self, module_spec: ModuleSpec) -> bool:
        """
        Register a compiled module.

        Args:
            module_spec: ModuleSpec to register

        Returns:
            True if successful, False otherwise
        """
        try:
            # Save module spec to file
            module_file = os.path.join(self.modules_path, f"{module_spec.module_id}.json")
            with open(module_file, 'w', encoding='utf-8') as f:
                f.write(module_spec.to_json())

            # Update index
            self.index["modules"][module_spec.module_id] = {
                "module_id": module_spec.module_id,
                "source_path": module_spec.source_path,
                "version_hash": module_spec.version_hash,
                "compiled_at": module_spec.compiled_at,
                "capabilities": [cap.name for cap in module_spec.capabilities],
                "deterministic": module_spec.has_deterministic_capabilities(),
                "requires_network": module_spec.requires_network(),
                "verification_status": module_spec.verification_status,
                "is_partial": module_spec.is_partial,
            }

            # Update capability index
            for cap in module_spec.capabilities:
                if cap.name not in self.index["capabilities"]:
                    self.index["capabilities"][cap.name] = []

                self.index["capabilities"][cap.name].append({
                    "module_id": module_spec.module_id,
                    "deterministic": cap.is_deterministic(),
                    "requires_network": cap.requires_network(),
                })

            # Save index
            self._save_index()

            return True

        except Exception as exc:
            logger.info(f"Failed to register module {module_spec.module_id}: {exc}")
            return False

    def get(self, module_id: str) -> Optional[ModuleSpec]:
        """
        Get module spec by ID.

        Args:
            module_id: Module ID

        Returns:
            ModuleSpec if found, None otherwise
        """
        try:
            module_file = os.path.join(self.modules_path, f"{module_id}.json")
            if not os.path.exists(module_file):
                return None

            with open(module_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return ModuleSpec.from_dict(data)

        except Exception as exc:
            logger.info(f"Failed to load module {module_id}: {exc}")
            return None

    def list_modules(
        self,
        deterministic_only: bool = False,
        network_required: Optional[bool] = None,
        verification_status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all registered modules.

        Args:
            deterministic_only: Only return deterministic modules
            network_required: Filter by network requirement
            verification_status: Filter by verification status

        Returns:
            List of module metadata
        """
        modules = []

        for module_id, metadata in self.index["modules"].items():
            # Apply filters
            if deterministic_only and not metadata["deterministic"]:
                continue

            if network_required is not None:
                if metadata["requires_network"] != network_required:
                    continue

            if verification_status and metadata["verification_status"] != verification_status:
                continue

            modules.append(metadata)

        return modules

    def search_capabilities(
        self,
        query: str,
        deterministic_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search for capabilities by name.

        Args:
            query: Search query (substring match)
            deterministic_only: Only return deterministic capabilities

        Returns:
            List of matching capabilities with module info
        """
        results = []

        query_lower = query.lower()

        for cap_name, providers in self.index["capabilities"].items():
            if query_lower in cap_name.lower():
                for provider in providers:
                    # Apply filters
                    if deterministic_only and not provider["deterministic"]:
                        continue

                    results.append({
                        "capability": cap_name,
                        "module_id": provider["module_id"],
                        "deterministic": provider["deterministic"],
                        "requires_network": provider["requires_network"],
                    })

        return results

    def get_capability(self, capability_name: str) -> Optional[Capability]:
        """
        Get capability details by name.

        Args:
            capability_name: Capability name

        Returns:
            Capability object if found, None otherwise
        """
        # Find module providing this capability
        if capability_name not in self.index["capabilities"]:
            return None

        providers = self.index["capabilities"][capability_name]
        if not providers:
            return None

        # Get first provider
        module_id = providers[0]["module_id"]
        module_spec = self.get(module_id)

        if not module_spec:
            return None

        return module_spec.get_capability(capability_name)

    def remove(self, module_id: str) -> bool:
        """
        Remove module from registry.

        Args:
            module_id: Module ID to remove

        Returns:
            True if successful, False otherwise
        """
        try:
            # Remove module file
            module_file = os.path.join(self.modules_path, f"{module_id}.json")
            if os.path.exists(module_file):
                os.remove(module_file)

            # Remove from index
            if module_id in self.index["modules"]:
                # Get capabilities to remove from capability index
                capabilities = self.index["modules"][module_id]["capabilities"]

                # Remove from modules index
                del self.index["modules"][module_id]

                # Remove from capability index
                for cap_name in capabilities:
                    if cap_name in self.index["capabilities"]:
                        self.index["capabilities"][cap_name] = [
                            p for p in self.index["capabilities"][cap_name]
                            if p["module_id"] != module_id
                        ]

                        # Remove capability if no providers left
                        if not self.index["capabilities"][cap_name]:
                            del self.index["capabilities"][cap_name]

                # Save index
                self._save_index()

            return True

        except Exception as exc:
            logger.info(f"Failed to remove module {module_id}: {exc}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Dictionary with statistics
        """
        total_modules = len(self.index["modules"])
        total_capabilities = len(self.index["capabilities"])

        deterministic_modules = sum(
            1 for m in self.index["modules"].values()
            if m["deterministic"]
        )

        verified_modules = sum(
            1 for m in self.index["modules"].values()
            if m["verification_status"] == "passed"
        )

        return {
            "total_modules": total_modules,
            "total_capabilities": total_capabilities,
            "deterministic_modules": deterministic_modules,
            "verified_modules": verified_modules,
            "partial_modules": sum(
                1 for m in self.index["modules"].values()
                if m["is_partial"]
            ),
        }

    def _load_index(self) -> Dict[str, Any]:
        """Load index from file"""
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as exc:
                logger.debug("Suppressed exception: %s", exc)
                pass

        # Return empty index
        return {
            "version": "1.0.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "modules": {},
            "capabilities": {},
        }

    def _save_index(self):
        """Save index to file"""
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, indent=2)
        except Exception as exc:
            logger.info(f"Failed to save index: {exc}")
