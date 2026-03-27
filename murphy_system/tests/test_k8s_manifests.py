# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
"""
Murphy System — Kubernetes Manifest Validation Tests

Validates that all K8s manifests in murphy_system/k8s/ meet production requirements.
Requires PyYAML (already in requirements_murphy_1.0.txt as pyyaml>=6.0.1).
"""

import os
import unittest

import yaml

# Path to k8s manifests directory
_K8S_DIR = os.path.join(os.path.dirname(__file__), "..", "k8s")


def _load(filename: str) -> dict:
    """Load and parse a YAML manifest file."""
    path = os.path.join(_K8S_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get(obj, *keys, default=None):
    """Safely traverse nested dicts/lists."""
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key, default)
        elif isinstance(obj, list) and isinstance(key, int):
            try:
                obj = obj[key]
            except IndexError:
                return default
        else:
            return default
        if obj is None:
            return default
    return obj


class TestDeploymentManifest(unittest.TestCase):
    """Validates deployment.yaml meets production requirements."""

    def setUp(self):
        self.doc = _load("deployment.yaml")

    def test_rolling_update_strategy(self):
        """deployment.yaml must use RollingUpdate strategy."""
        strategy_type = _get(self.doc, "spec", "strategy", "type")
        self.assertEqual(strategy_type, "RollingUpdate")

    def test_readonly_root_filesystem(self):
        """Container securityContext must set readOnlyRootFilesystem: true."""
        containers = _get(self.doc, "spec", "template", "spec", "containers", default=[])
        found = any(
            _get(c, "securityContext", "readOnlyRootFilesystem") is True
            for c in containers
        )
        self.assertTrue(found, "No container has readOnlyRootFilesystem: true")

    def test_run_as_non_root(self):
        """Pod securityContext must set runAsNonRoot: true."""
        run_as_non_root = _get(
            self.doc, "spec", "template", "spec", "securityContext", "runAsNonRoot"
        )
        self.assertTrue(run_as_non_root, "Pod securityContext.runAsNonRoot is not true")

    def test_resource_requests_and_limits(self):
        """All containers must define resource requests and limits."""
        containers = _get(self.doc, "spec", "template", "spec", "containers", default=[])
        for c in containers:
            resources = _get(c, "resources", default={})
            self.assertIn("requests", resources, f"Container {c.get('name')} missing resources.requests")
            self.assertIn("limits", resources, f"Container {c.get('name')} missing resources.limits")

    def test_liveness_probe_configured(self):
        """All containers must define a livenessProbe."""
        containers = _get(self.doc, "spec", "template", "spec", "containers", default=[])
        for c in containers:
            self.assertIn("livenessProbe", c, f"Container {c.get('name')} missing livenessProbe")

    def test_readiness_probe_configured(self):
        """All containers must define a readinessProbe."""
        containers = _get(self.doc, "spec", "template", "spec", "containers", default=[])
        for c in containers:
            self.assertIn("readinessProbe", c, f"Container {c.get('name')} missing readinessProbe")

    def test_image_uses_ghcr(self):
        """Container image must reference ghcr.io registry."""
        containers = _get(self.doc, "spec", "template", "spec", "containers", default=[])
        for c in containers:
            image = c.get("image", "")
            self.assertIn("ghcr.io", image, f"Container {c.get('name')} image does not use ghcr.io: {image}")


class TestNetworkPolicyManifest(unittest.TestCase):
    """Validates network-policy.yaml exists and is properly configured."""

    def setUp(self):
        self.doc = _load("network-policy.yaml")

    def test_file_exists(self):
        """network-policy.yaml must exist."""
        self.assertIsNotNone(self.doc)

    def test_policy_types_include_ingress_and_egress(self):
        """policyTypes must include both Ingress and Egress."""
        policy_types = _get(self.doc, "spec", "policyTypes", default=[])
        self.assertIn("Ingress", policy_types, "policyTypes must include Ingress")
        self.assertIn("Egress", policy_types, "policyTypes must include Egress")


class TestPodDisruptionBudgetManifest(unittest.TestCase):
    """Validates pdb.yaml exists and is properly configured."""

    def setUp(self):
        self.doc = _load("pdb.yaml")

    def test_file_exists(self):
        """pdb.yaml must exist."""
        self.assertIsNotNone(self.doc)

    def test_min_available_is_set(self):
        """PDB must define minAvailable."""
        min_available = _get(self.doc, "spec", "minAvailable")
        self.assertIsNotNone(min_available, "spec.minAvailable must be set")


class TestIngressManifest(unittest.TestCase):
    """Validates ingress.yaml is properly configured for production."""

    def setUp(self):
        self.doc = _load("ingress.yaml")

    def test_ingress_class_name_set(self):
        """ingress.yaml must define ingressClassName."""
        ingress_class = _get(self.doc, "spec", "ingressClassName")
        self.assertIsNotNone(ingress_class, "spec.ingressClassName must be set")


class TestSecretManifest(unittest.TestCase):
    """Validates secret.yaml has all required keys."""

    REQUIRED_KEYS = [
        "DATABASE_URL",
        "REDIS_URL",
        "GROQ_API_KEY",
        "MURPHY_JWT_SECRET",
        "ENCRYPTION_KEY",
        "GITHUB_TOKEN",
        "STRIPE_API_KEY",
        "MURPHY_API_KEYS",
        "MURPHY_CREDENTIAL_MASTER_KEY",
    ]

    def setUp(self):
        self.doc = _load("secret.yaml")

    def test_all_required_keys_present(self):
        """secret.yaml must contain all required secret keys."""
        data = _get(self.doc, "data", default={})
        for key in self.REQUIRED_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, data, f"secret.yaml missing required key: {key}")


class TestAllManifestsLoadable(unittest.TestCase):
    """Validates that all YAML files in k8s/ are parseable."""

    def test_all_yaml_files_parseable(self):
        """All .yaml files in k8s/ must be loadable without error."""
        yaml_files = [f for f in os.listdir(_K8S_DIR) if f.endswith(".yaml")]
        self.assertGreater(len(yaml_files), 0, "No YAML files found in k8s/ directory")
        for fname in yaml_files:
            with self.subTest(file=fname):
                doc = _load(fname)
                self.assertIsNotNone(doc, f"{fname} parsed to None")


if __name__ == "__main__":
    unittest.main()

