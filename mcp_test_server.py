from mcp.server.fastmcp import FastMCP
import random
import torch
import torch.nn as nn

mcp = FastMCP("aviz-mock-ai-agent")

# -----------------------------
# 1. MOCK SONiC TELEMETRY TOOL
# -----------------------------
@mcp.tool()
def get_port_telemetry() -> dict:
    """Simulate SONiC port telemetry metrics."""
    telemetry = {
        "switch": "sonic-leaf-01",
        "interface": "Ethernet12",
        "rx_bytes": random.randint(10_000, 10_000_000),
        "tx_bytes": random.randint(10_000, 10_000_000),
        "rx_errors": random.randint(0, 10),
        "tx_errors": random.randint(0, 10),
        "utilization": round(random.uniform(0.2, 0.95), 2),
    }
    return telemetry


# -------------------------------------
# 2. GPU-ACCELERATED AI ANALYSIS TOOL
# -------------------------------------
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

# Preload the model and force it to use MPS if available
device = "mps" if torch.backends.mps.is_available() else "cpu"
model = SimpleHealthModel().to(device)
model.eval()

@mcp.tool()
def predict_link_health(rx_errors: int, tx_errors: int, utilization: float) -> dict:
    """Run AI model to predict overall link health based on telemetry."""
    with torch.no_grad():
        x = torch.tensor([[rx_errors, tx_errors, utilization]], dtype=torch.float32).to(device)
        score = model(x).item()
    return {
        "health_score": round(score, 3),
        "status": "healthy" if score > 0.7 else "warning"
    }


# -------------------------------------
# ENTRY POINT
# -------------------------------------
if __name__ == "__main__":
    print("Running Aviz AI Agent prototype...")
    print(f"Using device: {device}")
    print("Waiting for requests on stdio")
    mcp.run()
