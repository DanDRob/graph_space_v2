import torch
import torch.nn as nn
import torch.nn.functional as F
import networkx as nx
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Callable
import time
import os

from graph_space_v2.ai.gnn.gnn_model import GNNModel


class GNNTrainer:
    def __init__(
        self,
        model: GNNModel,
        learning_rate: float = 0.01,
        weight_decay: float = 5e-4
    ):
        self.model = model
        self.optimizer = torch.optim.Adam(
            self.model.model.parameters(),
            lr=learning_rate,
            weight_decay=weight_decay
        )
        self.loss_fn = nn.MSELoss()
        self.training_stats = []

    def train_step(self, data: torch.Tensor) -> float:
        self.model.model.train()
        self.optimizer.zero_grad()

        # Forward pass
        output = self.model.model(data.x, data.edge_index, data.edge_attr)

        # Compute loss (reconstruction loss for node embeddings)
        # Here we use a simple autoencoder-style loss for unsupervised learning
        loss = self.loss_fn(output, data.x)

        # Backward pass
        loss.backward()
        self.optimizer.step()

        return loss.item()

    def train(
        self,
        graph: nx.Graph,
        epochs: int = 100,
        progress_callback: Optional[Callable[[int, int, float], None]] = None
    ) -> Dict[str, Any]:
        """
        Train the GNN model on a given graph.

        Args:
            graph: NetworkX graph to train on
            epochs: Number of training epochs
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with training statistics
        """
        start_time = time.time()
        data = self.model._prepare_data(graph)

        losses = []
        for epoch in range(epochs):
            loss = self.train_step(data)
            losses.append(loss)

            if progress_callback:
                progress_callback(epoch, epochs, loss)

            # Print progress every 10 epochs
            if (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch+1}/{epochs}, Loss: {loss:.6f}")

        # Generate final embeddings
        self.model.predict(graph)

        training_time = time.time() - start_time
        stats = {
            "epochs": epochs,
            "final_loss": losses[-1],
            "training_time": training_time,
            "loss_history": losses
        }

        self.training_stats.append(stats)
        return stats

    def save_checkpoint(self, path: str) -> None:
        """Save trainer checkpoint including model and optimizer state"""
        os.makedirs(os.path.dirname(path), exist_ok=True)

        checkpoint = {
            'optimizer_state_dict': self.optimizer.state_dict(),
            'training_stats': self.training_stats,
        }

        # Save model first
        model_path = path.replace('.pt', '_model.pt')
        self.model.save(model_path)

        # Save trainer state
        torch.save(checkpoint, path)

    def load_checkpoint(self, path: str) -> None:
        """Load trainer checkpoint including model and optimizer state"""
        # Load model first
        model_path = path.replace('.pt', '_model.pt')
        self.model.load(model_path)

        # Recreate optimizer with loaded model parameters
        self.optimizer = torch.optim.Adam(
            self.model.model.parameters(),
            lr=self.optimizer.param_groups[0]['lr']
        )

        # Load trainer state
        checkpoint = torch.load(path, map_location=self.model.device)
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.training_stats = checkpoint['training_stats']
