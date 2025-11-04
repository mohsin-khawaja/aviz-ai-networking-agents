# Aviz NCP AI Agent

This repository contains a prototype implementation of a **Model Context Protocol (MCP)** server that simulates Aviz Networks' **Network Co-Pilot (NCP)** AI infrastructure. This agent demonstrates capabilities for validating builds, monitoring multi-vendor telemetry, and predicting link health across SONiC and non-SONiC network devices.

## Overview

Aviz Networks builds open, modular, and cloud-managed network solutions. NCP manages SONiC switches (~5% of the system) alongside non-SONiC switches, firewalls, and other network elements, making it a **vendor-agnostic** platform.

This agent serves as a starting point for understanding how Aviz's AI agents interact with multi-vendor network data pipelines through the MCP interface. The implementation is designed to be modular, testable, and ready for integration with real gNMI telemetry and Ansible workflows.

## Architecture

The project follows a modular design with clear separation of concerns:

```
aviz_agents/
├── agents/              # Agent modules
│   ├── telemetry_agent.py    # Network telemetry collection
│   ├── ai_agent.py           # AI-based health prediction
│   └── build_agent.py        # Build metadata validation
├── utils/               # Utility modules
│   └── logger.py             # Consistent logging
├── mcp_test_server.py   # Main MCP server
├── client_test.py       # Test client
└── README.md
```

## Features

- **MCP Server (FastMCP)** implementation for agent communication
- **Multi-vendor support**: SONiC, Cisco, FortiGate, and other device types
- **GPU-accelerated AI**: PyTorch-based link health prediction with MPS support (Mac)
- **Build validation**: Validates both SONiC and non-SONiC build metadata
- **Modular design**: Self-contained, testable agent modules
- **Comprehensive logging**: Structured logging via Python `logging` module

## Installation

Clone the repository and set up a Python virtual environment:

```bash
git clone https://github.com/mohsin-khawaja/ai-networking-sandbox.git
cd ai-networking-sandbox
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install "mcp[cli]" torch
```

**Requirements:**
- Python 3.10+
- MCP SDK (`mcp[cli]`)
- PyTorch (for AI predictions)

## Available Tools

The MCP server exposes four tools for network management and AI analysis:

### 1. `get_port_telemetry()`

Simulates SONiC port telemetry metrics collection.

**Returns:**
```json
{
  "switch": "sonic-leaf-01",
  "interface": "Ethernet12",
  "rx_bytes": 1234567,
  "tx_bytes": 2345678,
  "rx_errors": 2,
  "tx_errors": 5,
  "utilization": 0.85
}
```

**Usage:**
```python
# Called via MCP client
result = await client.call_tool("get_port_telemetry", {})
```

### 2. `get_network_topology()`

Returns a mock network topology with multiple device types, simulating a multi-vendor network environment.

**Returns:**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "devices": [
    {
      "id": "sonic-leaf-01",
      "type": "SONiC",
      "vendor": "Dell",
      "model": "S5248F-ON",
      "role": "leaf",
      "status": "active",
      "interfaces": [...]
    },
    ...
  ],
  "links": [...],
  "statistics": {
    "total_devices": 5,
    "sonic_devices": 2,
    "non_sonic_devices": 3,
    "total_links": 3,
    "active_links": 3
  }
}
```

**Usage:**
```python
result = await client.call_tool("get_network_topology", {})
```

### 3. `predict_link_health(rx_errors, tx_errors, utilization)`

Runs an AI model to predict overall link health based on telemetry metrics. Uses a PyTorch neural network with GPU acceleration (MPS on Mac).

**Parameters:**
- `rx_errors` (int): Number of receive errors
- `tx_errors` (int): Number of transmit errors
- `utilization` (float): Link utilization (0.0 to 1.0)

**Returns:**
```json
{
  "health_score": 0.823,
  "status": "healthy"
}
```

**Usage:**
```python
result = await client.call_tool("predict_link_health", {
  "rx_errors": 2,
  "tx_errors": 5,
  "utilization": 0.85
})
```

### 4. `validate_build_metadata(build_json_path)`

Validates SONiC or non-SONiC build JSON files by checking for required fields and structure.

**Parameters:**
- `build_json_path` (str): Path to the build JSON file

**Returns:**
```json
{
  "valid": true,
  "device_type": "SONiC",
  "errors": [],
  "warnings": ["Recommended field missing: serial_number"],
  "metadata": {...}
}
```

**Usage:**
```python
result = await client.call_tool("validate_build_metadata", {
  "build_json_path": "sample_builds/sonic_build.json"
})
```

## Running the Agent

### Start the MCP Server

```bash
python mcp_test_server.py
```

The server will wait for requests on stdio and log initialization information.

### Test with Client

```bash
python client_test.py
```

The test client demonstrates:
1. MCP connection initialization
2. Telemetry collection
3. AI health prediction

## Project Structure

### Agents

Each agent module is self-contained and testable:

- **`agents/telemetry_agent.py`**: Handles network telemetry collection and topology generation
- **`agents/ai_agent.py`**: Contains the PyTorch model and health prediction logic
- **`agents/build_agent.py`**: Validates build metadata for SONiC and non-SONiC devices

### Utilities

- **`utils/logger.py`**: Provides consistent logging configuration across all modules

## Design Philosophy

- **Modularity**: Each agent is self-contained and can be tested independently
- **Vendor-agnostic**: Designed to work with SONiC (~5%) and non-SONiC devices (~95%)
- **Logging**: Structured logging for debugging and monitoring
- **Backend-focused**: No UI work; focus on core functionality
- **Future-ready**: Prepared for integration with:
  - Real gNMI telemetry streams
  - Ansible automation workflows
  - Production NCP infrastructure

## Development

### Adding New Tools

1. Create or extend an agent module in `agents/`
2. Import the function in `mcp_test_server.py`
3. Register it with `@mcp.tool()` decorator
4. Update this README with tool documentation

### Logging

All modules use the centralized logger from `utils/logger.py`:

```python
from utils.logger import setup_logger

logger = setup_logger(__name__)
logger.info("Your log message")
```

### Testing

Test individual agents:

```python
from agents.telemetry_agent import get_network_topology
topology = get_network_topology()
```

## Future Integration

This prototype is designed to evolve into production-ready components:

- **gNMI Integration**: Replace mock telemetry with real gNMI streams
- **Ansible Integration**: Add automation workflows for device management
- **Multi-agent Orchestration**: Coordinate multiple specialized agents
- **Real-time Monitoring**: Stream telemetry data for continuous analysis

## License

See repository for license information.

## Contributing

This is a prototype for Aviz Networks' NCP platform. For contributions, please follow the project's contribution guidelines.
