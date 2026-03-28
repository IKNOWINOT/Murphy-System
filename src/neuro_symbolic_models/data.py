"""
Data Collection and Processing
===============================

Collects training data from Synthetic Failure Generator
and prepares it for model training.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests
import torch
from torch_geometric.data import Data, Dataset

logger = logging.getLogger("neuro_symbolic_models.data")


@dataclass
class TrainingExample:
    """Single training example."""
    graph: Data  # PyTorch Geometric Data object
    symbolic_features: np.ndarray
    labels: Dict[str, float]  # H, D, R ground truth
    metadata: Dict[str, Any]


@dataclass
class GraphFeatures:
    """Features for graph representation."""
    node_features: np.ndarray  # [num_nodes, node_feature_dim]
    edge_index: np.ndarray  # [2, num_edges]
    edge_features: Optional[np.ndarray] = None  # [num_edges, edge_feature_dim]
    global_features: Optional[np.ndarray] = None


class TrainingDataCollector:
    """
    Collects training data from Synthetic Failure Generator.
    """

    def __init__(
        self,
        failure_generator_url: str = "http://localhost:8059",
        node_feature_dim: int = 64,
        symbolic_feature_dim: int = 32
    ):
        self.failure_generator_url = failure_generator_url
        self.node_feature_dim = node_feature_dim
        self.symbolic_feature_dim = symbolic_feature_dim

    def collect_training_batch(
        self,
        batch_size: int = 1000,
        failure_types: Optional[List[str]] = None
    ) -> List[TrainingExample]:
        """
        Collect labeled training examples from failure generator.

        Args:
            batch_size: Number of examples to collect
            failure_types: Specific failure types to collect (optional)

        Returns:
            List of training examples
        """
        examples = []

        try:
            # Request synthetic failures
            response = requests.post(
                f"{self.failure_generator_url}/generate/batch",
                json={
                    "count": batch_size,
                    "failure_types": failure_types
                },
                timeout=30
            )

            if response.status_code != 200:
                logger.info(f"Failed to collect data: {response.status_code}")
                return examples

            failures = response.json().get("failures", [])

            for failure in failures:
                try:
                    example = self._process_failure(failure)
                    examples.append(example)
                except Exception as exc:
                    logger.info(f"Failed to process failure: {exc}")
                    continue

        except Exception as exc:
            logger.info(f"Failed to collect training batch: {exc}")

        return examples

    def _process_failure(self, failure: Dict[str, Any]) -> TrainingExample:
        """
        Process a single failure into a training example.
        """
        # Extract graph structure
        graph = self._construct_graph(failure)

        # Extract symbolic features
        symbolic_features = self._extract_symbolic_features(failure)

        # Extract ground truth labels
        labels = self._extract_labels(failure)

        return TrainingExample(
            graph=graph,
            symbolic_features=symbolic_features,
            labels=labels,
            metadata=failure.get("metadata", {})
        )

    def _construct_graph(self, failure: Dict[str, Any]) -> Data:
        """
        Construct PyTorch Geometric Data object from failure.
        """
        # Extract artifact graph (simplified - in practice, parse from failure data)
        num_nodes = 10  # simplified graph size
        node_features = np.random.randn(num_nodes, self.node_feature_dim)

        # Create edges (simplified)
        edge_index = np.array([
            [0, 1, 2, 3, 4, 5, 6, 7, 8],
            [1, 2, 3, 4, 5, 6, 7, 8, 9]
        ])

        # Convert to PyTorch tensors
        x = torch.tensor(node_features, dtype=torch.float)
        edge_index = torch.tensor(edge_index, dtype=torch.long)

        return Data(x=x, edge_index=edge_index)

    def _extract_symbolic_features(self, failure: Dict[str, Any]) -> np.ndarray:
        """
        Extract symbolic features from failure.

        Features include:
        - Rule satisfiability flags
        - Contradiction counts
        - Verification success rates
        - Interface reliability stats
        """
        features = np.zeros(self.symbolic_feature_dim)

        # Extract from failure data
        confidence_profile = failure.get("confidence_drift_profile", {})

        # Rule features (first quarter)
        features[0] = len(failure.get("violated_assumptions", []))
        features[1] = len(failure.get("missed_gates", []))
        features[2] = len(failure.get("recommended_gates", []))

        # Contradiction features (second quarter)
        features[8] = 1.0 if "conflict" in failure.get("root_cause", "").lower() else 0.0
        features[9] = 1.0 if "ambiguous" in failure.get("root_cause", "").lower() else 0.0

        # Verification features (third quarter)
        grounding_scores = confidence_profile.get("grounding_scores", [0.5])
        features[16] = np.mean(grounding_scores)
        features[17] = np.std(grounding_scores)

        # Reliability features (fourth quarter)
        features[24] = failure.get("murphy_probability", 0.5)
        features[25] = failure.get("expected_loss", 0.5)

        return features

    def _extract_labels(self, failure: Dict[str, Any]) -> Dict[str, float]:
        """
        Extract ground truth labels from failure.
        """
        confidence_profile = failure.get("confidence_drift_profile", {})

        # Instability: use final instability score
        instability_scores = confidence_profile.get("instability_scores", [0.5])
        H = instability_scores[-1] if instability_scores else 0.5

        # Grounding: use final grounding score
        grounding_scores = confidence_profile.get("grounding_scores", [0.5])
        D = grounding_scores[-1] if grounding_scores else 0.5

        # Risk: use Murphy probability
        R = failure.get("murphy_probability", 0.5)

        return {
            "H": float(H),
            "D": float(D),
            "R": float(R)
        }

    def collect_historical_disasters(self) -> List[TrainingExample]:
        """
        Collect training data from historical disaster replays.
        """
        examples = []

        disasters = ["mcas", "flash_crash", "therac25"]

        for disaster in disasters:
            try:
                response = requests.post(
                    f"{self.failure_generator_url}/test/historical",
                    json={"disaster_name": disaster},
                    timeout=30
                )

                if response.status_code == 200:
                    result = response.json()
                    # Process historical disaster result
                    # (simplified - in practice, extract full failure sequence)
                    logger.info(f"Collected historical disaster: {disaster}")

            except Exception as exc:
                logger.info(f"Failed to collect historical disaster {disaster}: {exc}")

        return examples


class GraphDataset(Dataset):
    """
    PyTorch Geometric Dataset for graph-based training.
    """

    def __init__(
        self,
        examples: List[TrainingExample],
        transform=None,
        pre_transform=None
    ):
        super().__init__(None, transform, pre_transform)
        self.examples = examples

    def len(self) -> int:
        return len(self.examples)

    def get(self, idx: int) -> Data:
        """
        Get a single example.
        """
        example = self.examples[idx]

        # Add labels to Data object
        data = example.graph
        data.y = torch.tensor([
            example.labels["H"],
            example.labels["D"],
            example.labels["R"]
        ], dtype=torch.float)

        # Add symbolic features
        data.symbolic_features = torch.tensor(
            example.symbolic_features,
            dtype=torch.float
        )

        return data


class DataAugmenter:
    """
    Augments training data with perturbations.
    """

    def __init__(self, noise_level: float = 0.1):
        self.noise_level = noise_level

    def augment(self, data: Data) -> Data:
        """
        Augment a single data example.
        """
        # Add noise to node features
        noise = torch.randn_like(data.x) * self.noise_level
        data.x = data.x + noise

        # Add noise to symbolic features
        symbolic_noise = torch.randn_like(data.symbolic_features) * self.noise_level
        data.symbolic_features = data.symbolic_features + symbolic_noise

        return data


class DataSplitter:
    """
    Splits data into train/val/test sets.
    """

    @staticmethod
    def split(
        examples: List[TrainingExample],
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        shuffle: bool = True
    ) -> Tuple[List[TrainingExample], List[TrainingExample], List[TrainingExample]]:
        """
        Split examples into train/val/test sets.
        """
        if abs(train_ratio + val_ratio + test_ratio - 1.0) >= 1e-6:
            raise ValueError("train_ratio + val_ratio + test_ratio must equal 1.0")

        n = len(examples)
        indices = np.arange(n)

        if shuffle:
            np.random.shuffle(indices)

        train_end = int(n * train_ratio)
        val_end = train_end + int(n * val_ratio)

        train_indices = indices[:train_end]
        val_indices = indices[train_end:val_end]
        test_indices = indices[val_end:]

        train_examples = [examples[i] for i in train_indices]
        val_examples = [examples[i] for i in val_indices]
        test_examples = [examples[i] for i in test_indices]

        return train_examples, val_examples, test_examples


class DataCache:
    """
    Caches training data to disk for faster loading.
    """

    def __init__(self, cache_dir: str = "./data/cache"):
        self.cache_dir = cache_dir
        import os
        os.makedirs(cache_dir, exist_ok=True)

    def save(self, examples: List[TrainingExample], name: str):
        """Save examples to cache."""
        cache_path = f"{self.cache_dir}/{name}.pt"
        torch.save(examples, cache_path)
        logger.info(f"Saved {len(examples)} examples to {cache_path}")

    def load(self, name: str) -> Optional[List[TrainingExample]]:
        """Load examples from cache."""
        cache_path = f"{self.cache_dir}/{name}.pt"

        try:
            examples = torch.load(cache_path)
            logger.info(f"Loaded {len(examples)} examples from {cache_path}")
            return examples
        except FileNotFoundError:
            logger.info(f"Cache not found: {cache_path}")
            return None


def create_dataloaders(
    train_examples: List[TrainingExample],
    val_examples: List[TrainingExample],
    batch_size: int = 32,
    num_workers: int = 4
):
    """
    Create PyTorch DataLoaders for training.
    """
    from torch_geometric.loader import DataLoader

    train_dataset = GraphDataset(train_examples)
    val_dataset = GraphDataset(val_examples)

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers
    )

    return train_loader, val_loader


# Example usage
if __name__ == "__main__":
    # Collect training data
    collector = TrainingDataCollector()
    examples = collector.collect_training_batch(batch_size=100)

    logger.info(f"Collected {len(examples)} training examples")

    # Split data
    train, val, test = DataSplitter.split(examples)
    logger.info(f"Train: {len(train)}, Val: {len(val)}, Test: {len(test)}")

    # Create dataloaders
    train_loader, val_loader = create_dataloaders(train, val, batch_size=16)
    logger.info(f"Created dataloaders with {len(train_loader)} train batches")
