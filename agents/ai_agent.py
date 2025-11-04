"""AI agent for link health prediction using PyTorch."""
import torch
import torch.nn as nn
from typing import Dict
from utils.logger import setup_logger

logger = setup_logger(__name__)


class SimpleHealthModel(nn.Module):
    """A lightweight feedforward model to estimate link health."""
    
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(3, 8),
            nn.ReLU(),
            nn.Linear(8, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        return self.net(x)


# Initialize model and device
device = "mps" if torch.backends.mps.is_available() else "cpu"
model = SimpleHealthModel().to(device)
model.eval()
logger.info(f"AI model initialized on device: {device}")


def predict_link_health(rx_errors: int, tx_errors: int, utilization: float) -> dict:
    """
    Run AI model to predict overall link health based on telemetry.
    
    Args:
        rx_errors: Number of receive errors
        tx_errors: Number of transmit errors
        utilization: Link utilization (0.0 to 1.0)
        
    Returns:
        Dictionary containing health_score and status
    """
    logger.info(f"Predicting link health: rx_errors={rx_errors}, tx_errors={tx_errors}, utilization={utilization}")
    
    with torch.no_grad():
        x = torch.tensor([[rx_errors, tx_errors, utilization]], dtype=torch.float32).to(device)
        score = model(x).item()
    
    result = {
        "health_score": round(score, 3),
        "status": "healthy" if score > 0.7 else "warning"
    }
    
    logger.debug(f"Health prediction: {result}")
    return result

