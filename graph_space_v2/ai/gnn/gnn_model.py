import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv
from torch_geometric.data import Data
import networkx as nx
import numpy as np
from typing import Dict, List, Optional, Tuple, Any


class GCN(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int, dropout: float = 0.1):
        super(GCN, self).__init__()

        self.conv1 = GCNConv(input_dim, hidden_dim)
        self.conv2 = GCNConv(hidden_dim, output_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x, edge_index, edge_weight=None):
        x = self.conv1(x, edge_index, edge_weight)
        x = F.relu(x)
        x = self.dropout(x)
        x = self.conv2(x, edge_index, edge_weight)
        return x


class GNNModel:
    def __init__(
        self,
        input_dim: int = 64,
        hidden_dim: int = 128,
        output_dim: int = 64,
        device: Optional[str] = None
    ):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim

        # Determine device
        if device is None:
            self.device = torch.device(
                'cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)

        # Initialize model
        self.model = GCN(input_dim, hidden_dim, output_dim).to(self.device)

        # Node ID to index mapping
        self.node_mapping: Dict[str, int] = {}
        self.reverse_mapping: Dict[int, str] = {}

        # Embedding cache
        self.embeddings: Optional[torch.Tensor] = None

    def _prepare_data(self, graph: nx.Graph) -> Data:
        # Reset node mappings
        self.node_mapping = {}
        self.reverse_mapping = {}

        # Map each node ID to a numeric index
        for i, node_id in enumerate(graph.nodes()):
            self.node_mapping[node_id] = i
            self.reverse_mapping[i] = node_id

        # Prepare edge index tensor
        edges = list(graph.edges())
        if not edges:
            # Handle case with no edges
            edge_index = torch.zeros((2, 0), dtype=torch.long)
            edge_weight = torch.zeros(0, dtype=torch.float)
        else:
            source_nodes = [self.node_mapping[e[0]] for e in edges]
            target_nodes = [self.node_mapping[e[1]] for e in edges]

            # Bidirectional edges for undirected graph
            edge_index = torch.tensor([
                source_nodes + target_nodes,
                target_nodes + source_nodes
            ], dtype=torch.long)

            # Edge weights
            weights = [graph.get_edge_data(
                *e).get('weight', 1.0) for e in edges]
            edge_weight = torch.tensor(weights + weights, dtype=torch.float)

        # Initialize random features if not present
        num_nodes = len(graph.nodes())
        x = torch.randn(num_nodes, self.input_dim)

        # Create PyG Data object
        data = Data(
            x=x,
            edge_index=edge_index,
            edge_attr=edge_weight
        ).to(self.device)

        return data

    def predict(self, graph: nx.Graph) -> Dict[str, np.ndarray]:
        self.model.eval()
        data = self._prepare_data(graph)

        with torch.no_grad():
            embeddings = self.model(data.x, data.edge_index, data.edge_attr)
            self.embeddings = embeddings

        # Convert to dictionary mapping node IDs to embeddings
        embedding_dict = {}
        for node_id, idx in self.node_mapping.items():
            embedding_dict[node_id] = embeddings[idx].cpu().numpy()

        return embedding_dict

    def get_node_embedding(self, node_id: str) -> Optional[np.ndarray]:
        if self.embeddings is None:
            return None

        if node_id not in self.node_mapping:
            return None

        idx = self.node_mapping[node_id]
        return self.embeddings[idx].cpu().numpy()

    def find_similar_nodes(self, node_id: str, k: int = 5) -> List[Tuple[str, float]]:
        if self.embeddings is None or node_id not in self.node_mapping:
            return []

        # Get the query embedding
        query_idx = self.node_mapping[node_id]
        query_embedding = self.embeddings[query_idx]

        # Compute similarities to all other nodes
        similarities = []
        for other_id, other_idx in self.node_mapping.items():
            if other_id == node_id:
                continue

            other_embedding = self.embeddings[other_idx]
            sim = F.cosine_similarity(
                query_embedding.unsqueeze(0),
                other_embedding.unsqueeze(0)
            ).item()

            similarities.append((other_id, sim))

        # Sort by similarity (descending) and take top k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:k]

    def save(self, path: str) -> None:
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'input_dim': self.input_dim,
            'hidden_dim': self.hidden_dim,
            'output_dim': self.output_dim,
            'node_mapping': self.node_mapping,
            'reverse_mapping': self.reverse_mapping,
        }, path)

    def load(self, path: str) -> None:
        checkpoint = torch.load(path, map_location=self.device)

        # Recreate model with saved dimensions
        self.input_dim = checkpoint['input_dim']
        self.hidden_dim = checkpoint['hidden_dim']
        self.output_dim = checkpoint['output_dim']

        self.model = GCN(
            self.input_dim,
            self.hidden_dim,
            self.output_dim
        ).to(self.device)

        # Load state dict
        self.model.load_state_dict(checkpoint['model_state_dict'])

        # Load mappings
        self.node_mapping = checkpoint['node_mapping']
        self.reverse_mapping = checkpoint['reverse_mapping']
