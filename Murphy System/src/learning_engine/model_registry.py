"""
Model Registry and Versioning

This module manages model versions and deployment.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from .model_architecture import ModelMetadata, ShadowAgentModel

logger = logging.getLogger(__name__)


@dataclass
class ModelVersion:
    """Represents a versioned model"""
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    version: str = "1.0.0"

    # Model info
    model_type: str = ""
    model_path: str = ""

    # Metadata
    metadata: ModelMetadata = field(default_factory=ModelMetadata)

    # Status
    status: str = "registered"  # registered, validated, deployed, archived

    # Deployment
    deployed_at: Optional[datetime] = None
    deployment_environment: str = ""  # dev, staging, production

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Tags and labels
    tags: List[str] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)

    # Performance tracking
    performance_metrics: Dict[str, float] = field(default_factory=dict)

    # Additional metadata
    extra_metadata: Dict[str, Any] = field(default_factory=dict)


class ModelRegistry:
    """Registry for managing model versions"""

    def __init__(self, registry_dir: str = "model_registry"):
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)

        self.models: Dict[UUID, ModelVersion] = {}
        self.deployed_models: Dict[str, ModelVersion] = {}  # env -> model

        self._load_registry()

    def register_model(
        self,
        model: ShadowAgentModel,
        name: str,
        version: str,
        tags: Optional[List[str]] = None
    ) -> ModelVersion:
        """Register a new model version"""

        logger.info(f"Registering model: {name} v{version}")

        # Create model version
        model_version = ModelVersion(
            name=name,
            version=version,
            model_type=model.metadata.model_type.value,
            metadata=model.metadata,
            tags=tags or [],
        )

        # Save model
        model_path = self._save_model(model, model_version)
        model_version.model_path = str(model_path)

        # Add to registry
        self.models[model_version.id] = model_version

        # Save registry
        self._save_registry()

        logger.info(f"Model registered: {model_version.id}")

        return model_version

    def get_model(self, model_id: UUID) -> Optional[ModelVersion]:
        """Get model by ID"""
        return self.models.get(model_id)

    def get_model_by_name(self, name: str, version: Optional[str] = None) -> Optional[ModelVersion]:
        """Get model by name and version"""

        matching_models = [
            m for m in self.models.values()
            if m.name == name and (version is None or m.version == version)
        ]

        if not matching_models:
            return None

        # Return latest version if version not specified
        return max(matching_models, key=lambda m: m.created_at)

    def list_models(
        self,
        name: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[ModelVersion]:
        """List models with optional filters"""

        models = list(self.models.values())

        if name:
            models = [m for m in models if m.name == name]

        if status:
            models = [m for m in models if m.status == status]

        if tags:
            models = [m for m in models if any(tag in m.tags for tag in tags)]

        return sorted(models, key=lambda m: m.created_at, reverse=True)

    def deploy_model(
        self,
        model_id: UUID,
        environment: str = "production"
    ) -> ModelVersion:
        """Deploy a model to an environment"""

        model = self.get_model(model_id)
        if not model:
            raise ValueError(f"Model not found: {model_id}")

        logger.info(f"Deploying model {model.name} v{model.version} to {environment}")

        # Update model status
        model.status = "deployed"
        model.deployed_at = datetime.now(timezone.utc)
        model.deployment_environment = environment
        model.updated_at = datetime.now(timezone.utc)

        # Track deployed model
        self.deployed_models[environment] = model

        # Save registry
        self._save_registry()

        logger.info(f"Model deployed to {environment}")

        return model

    def get_deployed_model(self, environment: str = "production") -> Optional[ModelVersion]:
        """Get currently deployed model for environment"""
        return self.deployed_models.get(environment)

    def archive_model(self, model_id: UUID):
        """Archive a model"""

        model = self.get_model(model_id)
        if not model:
            raise ValueError(f"Model not found: {model_id}")

        logger.info(f"Archiving model {model.name} v{model.version}")

        model.status = "archived"
        model.updated_at = datetime.now(timezone.utc)

        self._save_registry()

    def update_performance_metrics(
        self,
        model_id: UUID,
        metrics: Dict[str, float]
    ):
        """Update model performance metrics"""

        model = self.get_model(model_id)
        if not model:
            raise ValueError(f"Model not found: {model_id}")

        model.performance_metrics.update(metrics)
        model.updated_at = datetime.now(timezone.utc)

        self._save_registry()

    def compare_models(
        self,
        model_ids: List[UUID],
        metric: str = "validation_accuracy"
    ) -> Dict[UUID, float]:
        """Compare models by a metric"""

        comparison = {}

        for model_id in model_ids:
            model = self.get_model(model_id)
            if model:
                # Try to get metric from performance_metrics first
                if metric in model.performance_metrics:
                    comparison[model_id] = model.performance_metrics[metric]
                # Fall back to metadata
                elif hasattr(model.metadata, metric):
                    comparison[model_id] = getattr(model.metadata, metric)

        return comparison

    def _save_model(self, model: ShadowAgentModel, version: ModelVersion) -> Path:
        """Save model to disk"""

        # Create model directory
        model_dir = self.registry_dir / version.name / version.version
        model_dir.mkdir(parents=True, exist_ok=True)

        # Save model metadata
        metadata_path = model_dir / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump({
                "id": str(version.id),
                "name": version.name,
                "version": version.version,
                "model_type": version.model_type,
                "created_at": version.created_at.isoformat(),
                "train_accuracy": model.metadata.train_accuracy,
                "validation_accuracy": model.metadata.validation_accuracy,
            }, f, indent=2)

        return model_dir

    def _save_registry(self):
        """Save registry to disk"""

        registry_file = self.registry_dir / "registry.json"

        registry_data = {
            "models": {
                str(model_id): {
                    "id": str(version.id),
                    "name": version.name,
                    "version": version.version,
                    "model_type": version.model_type,
                    "model_path": version.model_path,
                    "status": version.status,
                    "created_at": version.created_at.isoformat(),
                    "tags": version.tags,
                }
                for model_id, version in self.models.items()
            },
            "deployed_models": {
                env: str(model.id)
                for env, model in self.deployed_models.items()
            }
        }

        with open(registry_file, 'w', encoding='utf-8') as f:
            json.dump(registry_data, f, indent=2)

    def _load_registry(self):
        """Load registry from disk"""

        registry_file = self.registry_dir / "registry.json"

        if not registry_file.exists():
            return

        try:
            with open(registry_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Load models
            for model_id_str, model_data in data.get("models", {}).items():
                model_id = UUID(model_id_str)
                # Reconstruct ModelVersion (simplified)
                # In production, would fully deserialize
                logger.info(f"Loaded model from registry: {model_data['name']}")

        except Exception as exc:
            logger.warning(f"Failed to load registry: {exc}")

    def get_registry_summary(self) -> Dict[str, Any]:
        """Get summary of registry"""

        return {
            "total_models": len(self.models),
            "deployed_models": len(self.deployed_models),
            "models_by_status": {
                status: len([m for m in self.models.values() if m.status == status])
                for status in ["registered", "validated", "deployed", "archived"]
            },
            "latest_model": max(
                self.models.values(),
                key=lambda m: m.created_at
            ).name if self.models else None,
        }
