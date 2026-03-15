"""
Neural Network Models for Confidence Estimation
================================================

Graph Neural Network architecture for learning:
- Epistemic instability H(x)
- Deterministic grounding D(x)
- Authority risk R(x)
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv, GraphSAGE, global_mean_pool

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for neuro-symbolic model."""
    node_feature_dim: int = 64
    edge_feature_dim: int = 16
    symbolic_feature_dim: int = 32
    hidden_dim: int = 128
    num_gnn_layers: int = 3
    num_attention_heads: int = 4
    dropout: float = 0.2
    output_dim: int = 3  # H, D, R


class SymbolicFeatureProcessor(nn.Module):
    """
    Processes symbolic features from existing system.

    Inputs:
    - Rule satisfiability flags
    - Contradiction counts
    - Verification success rates
    - Interface reliability stats
    """

    def __init__(self, input_dim: int, output_dim: int):
        super().__init__()

        self.input_dim = input_dim
        self.output_dim = output_dim

        # Separate encoders for different feature types
        feature_dim = input_dim // 4
        embed_dim = output_dim // 4

        self.rule_encoder = nn.Sequential(
            nn.Linear(feature_dim, embed_dim),
            nn.ReLU(),
            nn.Dropout(0.1)
        )

        self.contradiction_encoder = nn.Sequential(
            nn.Linear(feature_dim, embed_dim),
            nn.ReLU(),
            nn.Dropout(0.1)
        )

        self.verification_encoder = nn.Sequential(
            nn.Linear(feature_dim, embed_dim),
            nn.ReLU(),
            nn.Dropout(0.1)
        )

        self.reliability_encoder = nn.Sequential(
            nn.Linear(feature_dim, embed_dim),
            nn.ReLU(),
            nn.Dropout(0.1)
        )

        self.fusion = nn.Sequential(
            nn.Linear(output_dim, output_dim),
            nn.ReLU(),
            nn.LayerNorm(output_dim)
        )

    def forward(self, symbolic_features: torch.Tensor) -> torch.Tensor:
        """
        Process symbolic features.

        Args:
            symbolic_features: Tensor of shape [batch_size, input_dim]

        Returns:
            Processed features of shape [batch_size, output_dim]
        """
        feature_dim = self.input_dim // 4

        # Split symbolic features into 4 types
        rule_features = symbolic_features[:, :feature_dim]
        contradiction_features = symbolic_features[:, feature_dim:2*feature_dim]
        verification_features = symbolic_features[:, 2*feature_dim:3*feature_dim]
        reliability_features = symbolic_features[:, 3*feature_dim:]

        # Encode each type
        rule_embed = self.rule_encoder(rule_features)
        contradiction_embed = self.contradiction_encoder(contradiction_features)
        verification_embed = self.verification_encoder(verification_features)
        reliability_embed = self.reliability_encoder(reliability_features)

        # Concatenate and fuse
        combined = torch.cat([
            rule_embed,
            contradiction_embed,
            verification_embed,
            reliability_embed
        ], dim=-1)

        return self.fusion(combined)


class GraphEncoder(nn.Module):
    """
    Graph Neural Network encoder using GraphSAGE.
    """

    def __init__(self, config: ModelConfig):
        super().__init__()

        self.config = config

        # Initial projection
        self.input_proj = nn.Linear(
            config.node_feature_dim,
            config.hidden_dim
        )

        # GraphSAGE layers
        self.conv_layers = nn.ModuleList([
            GraphSAGE(
                in_channels=config.hidden_dim,
                hidden_channels=config.hidden_dim,
                num_layers=1,
                out_channels=config.hidden_dim
            )
            for _ in range(config.num_gnn_layers)
        ])

        # Layer normalization
        self.layer_norms = nn.ModuleList([
            nn.LayerNorm(config.hidden_dim)
            for _ in range(config.num_gnn_layers)
        ])

        # Dropout
        self.dropout = nn.Dropout(config.dropout)

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor
    ) -> torch.Tensor:
        """
        Encode graph structure.

        Args:
            x: Node features [num_nodes, node_feature_dim]
            edge_index: Edge indices [2, num_edges]

        Returns:
            Node embeddings [num_nodes, hidden_dim]
        """
        # Initial projection
        x = self.input_proj(x)
        x = F.relu(x)

        # Apply GNN layers with residual connections
        for conv, norm in zip(self.conv_layers, self.layer_norms):
            x_residual = x
            x = conv(x, edge_index)
            x = norm(x)
            x = F.relu(x)
            x = self.dropout(x)
            x = x + x_residual  # Residual connection

        return x


class AttentionPooling(nn.Module):
    """
    Attention-based graph pooling.
    """

    def __init__(self, hidden_dim: int, num_heads: int = 4):
        super().__init__()

        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_dim,
            num_heads=num_heads,
            dropout=0.1,
            batch_first=True
        )

        self.query = nn.Parameter(torch.randn(1, 1, hidden_dim))

    def forward(
        self,
        x: torch.Tensor,
        batch: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Pool node embeddings to graph embedding.

        Args:
            x: Node embeddings [num_nodes, hidden_dim]
            batch: Batch assignment [num_nodes]

        Returns:
            Graph embedding [batch_size, hidden_dim]
        """
        if batch is None:
            # Single graph
            x = x.unsqueeze(0)  # [1, num_nodes, hidden_dim]
            query = self.query  # [1, 1, hidden_dim]

            pooled, _ = self.attention(query, x, x)
            return pooled.squeeze(1)  # [1, hidden_dim]
        else:
            # Batch of graphs
            batch_size = batch.max().item() + 1
            pooled_list = []

            for i in range(batch_size):
                mask = (batch == i)
                x_i = x[mask].unsqueeze(0)  # [1, num_nodes_i, hidden_dim]
                query = self.query  # [1, 1, hidden_dim]

                pooled_i, _ = self.attention(query, x_i, x_i)
                pooled_list.append(pooled_i.squeeze(1))

            return torch.cat(pooled_list, dim=0)  # [batch_size, hidden_dim]


class NeuroSymbolicConfidenceModel(nn.Module):
    """
    Complete neuro-symbolic confidence model.

    Architecture:
    1. Graph Encoder (GNN)
    2. Symbolic Feature Processor
    3. Feature Fusion
    4. Multi-head Output (H, D, R)
    """

    def __init__(self, config: ModelConfig):
        super().__init__()

        self.config = config

        # Graph encoder
        self.graph_encoder = GraphEncoder(config)

        # Symbolic feature processor
        self.symbolic_processor = SymbolicFeatureProcessor(
            input_dim=config.symbolic_feature_dim,
            output_dim=config.hidden_dim
        )

        # Attention pooling
        self.attention_pool = AttentionPooling(
            hidden_dim=config.hidden_dim,
            num_heads=config.num_attention_heads
        )

        # Feature fusion
        self.fusion = nn.Sequential(
            nn.Linear(config.hidden_dim * 2, config.hidden_dim),
            nn.ReLU(),
            nn.LayerNorm(config.hidden_dim),
            nn.Dropout(config.dropout)
        )

        # Output heads
        self.instability_head = nn.Sequential(
            nn.Linear(config.hidden_dim, config.hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim // 2, 1),
            nn.Sigmoid()  # Output in [0,1]
        )

        self.grounding_head = nn.Sequential(
            nn.Linear(config.hidden_dim, config.hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim // 2, 1),
            nn.Sigmoid()
        )

        self.risk_head = nn.Sequential(
            nn.Linear(config.hidden_dim, config.hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim // 2, 1),
            nn.Sigmoid()
        )

    def forward(
        self,
        node_features: torch.Tensor,
        edge_index: torch.Tensor,
        symbolic_features: torch.Tensor,
        batch: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Forward pass.

        Args:
            node_features: Node features [num_nodes, node_feature_dim]
            edge_index: Edge indices [2, num_edges]
            symbolic_features: Symbolic features [batch_size, symbolic_feature_dim]
            batch: Batch assignment [num_nodes] (optional)

        Returns:
            (H_ml, D_ml, R_ml) - Instability, Grounding, Risk predictions
            Each of shape [batch_size, 1]
        """
        # Encode graph structure
        node_embeddings = self.graph_encoder(node_features, edge_index)

        # Pool to graph embedding
        graph_embedding = self.attention_pool(node_embeddings, batch)

        # Process symbolic features
        symbolic_embedding = self.symbolic_processor(symbolic_features)

        # Fuse graph and symbolic embeddings
        combined = torch.cat([graph_embedding, symbolic_embedding], dim=-1)
        fused = self.fusion(combined)

        # Multi-head prediction
        H_ml = self.instability_head(fused)
        D_ml = self.grounding_head(fused)
        R_ml = self.risk_head(fused)

        return H_ml, D_ml, R_ml

    def predict_with_confidence(
        self,
        node_features: torch.Tensor,
        edge_index: torch.Tensor,
        symbolic_features: torch.Tensor,
        batch: Optional[torch.Tensor] = None
    ) -> Dict[str, Any]:
        """
        Make prediction with confidence estimate.

        Returns:
            Dictionary with predictions and metadata
        """
        self.eval()

        with torch.no_grad():
            H_ml, D_ml, R_ml = self.forward(
                node_features,
                edge_index,
                symbolic_features,
                batch
            )

            # Estimate prediction confidence based on model uncertainty
            # (simplified - in practice, use ensemble or dropout-based uncertainty)
            prediction_confidence = torch.tensor([0.85])  # default confidence

            return {
                "H_ml": H_ml.item(),
                "D_ml": D_ml.item(),
                "R_ml": R_ml.item(),
                "prediction_confidence": prediction_confidence.item(),
                "model_version": "1.0.0"
            }


class ModelEnsemble(nn.Module):
    """
    Ensemble of multiple models for better uncertainty estimation.
    """

    def __init__(self, models: list):
        super().__init__()
        self.models = nn.ModuleList(models)

    def forward(
        self,
        node_features: torch.Tensor,
        edge_index: torch.Tensor,
        symbolic_features: torch.Tensor,
        batch: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Forward pass through ensemble.

        Returns:
            (H_mean, D_mean, R_mean, uncertainty)
        """
        H_predictions = []
        D_predictions = []
        R_predictions = []

        for model in self.models:
            H, D, R = model(node_features, edge_index, symbolic_features, batch)
            H_predictions.append(H)
            D_predictions.append(D)
            R_predictions.append(R)

        # Stack predictions
        H_stack = torch.stack(H_predictions)
        D_stack = torch.stack(D_predictions)
        R_stack = torch.stack(R_predictions)

        # Compute mean and std
        H_mean = H_stack.mean(dim=0)
        D_mean = D_stack.mean(dim=0)
        R_mean = R_stack.mean(dim=0)

        # Uncertainty as average std
        uncertainty = (
            H_stack.std(dim=0) +
            D_stack.std(dim=0) +
            R_stack.std(dim=0)
        ) / 3.0

        return H_mean, D_mean, R_mean, uncertainty


def create_model(config: Optional[ModelConfig] = None) -> NeuroSymbolicConfidenceModel:
    """
    Factory function to create model with default or custom config.
    """
    if config is None:
        config = ModelConfig()

    return NeuroSymbolicConfidenceModel(config)


def load_model(checkpoint_path: str) -> NeuroSymbolicConfidenceModel:
    """
    Load model from checkpoint.
    """
    checkpoint = torch.load(checkpoint_path)

    config = checkpoint.get("config", ModelConfig())
    model = create_model(config)
    model.load_state_dict(checkpoint["model_state_dict"])

    return model


def save_model(
    model: NeuroSymbolicConfidenceModel,
    checkpoint_path: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Save model to checkpoint.
    """
    checkpoint = {
        "model_state_dict": model.state_dict(),
        "config": model.config,
        "metadata": metadata or {}
    }

    torch.save(checkpoint, checkpoint_path)
