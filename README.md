# Aviz Network Co-Pilot (NCP) AI Agent Framework

This repository contains a production-ready prototype of an **AI agent framework** built on the **Model Context Protocol (MCP)** for Aviz Networks' **Network Co-Pilot (NCP)** platform. This framework demonstrates how AI-driven agents can provide vendor-agnostic observability, validation, and automation for enterprise network infrastructure.

## Overview

**Aviz Networks** builds open, modular, and cloud-managed network solutions. The **Network Co-Pilot (NCP)** platform manages a diverse mix of network devices:

- **SONiC switches** (~5% of deployments)
- **Non-SONiC switches** (Cisco, Arista, EdgeCore, etc.)
- **Firewalls** (FortiGate, Palo Alto, etc.)
- **Other network elements** (routers, load balancers, etc.)

NCP is designed to be **vendor-agnostic**, providing unified observability, validation, and automation across all device types. This AI agent framework simulates the infrastructure-level AI capabilities that power NCP's intelligent operations.

## Architecture

The project follows a modular, production-ready architecture:

```
aviz_agents/
├── agents/                    # AI agent modules
│   ├── telemetry_agent.py      # Network telemetry collection
│   ├── ai_agent.py             # ML-based health prediction
│   ├── build_agent.py          # Build metadata validation
│   ├── remediation_agent.py   # Automated remediation
│   ├── integration_tools.py    # Telnet and NetBox integration
│   └── validation_agent.py     # System health validation (AI ONE Center)
├── data/                       # Data files
│   ├── builds/                 # Build JSON samples (SONiC, Cisco, EdgeCore)
│   └── netbox_sample.json      # Sample NetBox topology data
├── utils/                      # Shared utilities
│   ├── logger.py               # Centralized logging
│   ├── file_loader.py          # JSON file loading
│   └── topology_builder.py     # Network topology generation
├── mcp_server.py               # Main MCP orchestrator
├── client_test.py              # Test client
└── README.md
```

Each agent module is self-contained, testable, and designed for integration with real NCP workflows.

## Installation

### Prerequisites

- Python 3.10 or higher
- Virtual environment (recommended)

### Setup

```bash
# Clone the repository
git clone https://github.com/mohsin-khawaja/ai-networking-sandbox.git
cd ai-networking-sandbox

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install "mcp[cli]" torch python-dotenv pyyaml

# Optional: For interactive CLI agent with LLM support
pip install openai tabulate

# Optional: For Telnet support in Python 3.12+ (telnetlib was removed)
pip install telnetlib3
```

**Optional: Configure Environment Variables**

Create a `.env` file in the project root for credentials (see `.env.example`):

```bash
# Copy example file
cp .env.example .env

# Edit .env with your credentials
# NETBOX_URL=https://demo.netbox.dev/api/
# NETBOX_TOKEN=your-token-here
# TELNET_HOST=192.168.1.100
# TELNET_USERNAME=admin
# TELNET_PASSWORD=password
```

## Available Tools

The MCP server exposes nine tools that demonstrate different aspects of NCP's AI infrastructure:

### 1. `get_port_telemetry()`

Simulates SONiC port telemetry metrics collection.

**Maps to NCP functionality:**
- Collects real-time interface statistics from SONiC switches
- Normalizes data for consumption by AI/ML models
- Supports integration with gNMI telemetry streams

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
result = await client.call_tool("get_port_telemetry", {})
```

### 2. `get_network_topology()`

Returns a mock network topology with multiple device types, demonstrating NCP's vendor-agnostic approach.

**Maps to NCP functionality:**
- Aggregates topology data from multiple vendor APIs
- Normalizes device and link information across vendors
- Provides unified view of network infrastructure
- Supports both SONiC (~5%) and non-SONiC devices (~95%)

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
    "total_links": 4,
    "active_links": 4
  }
}
```

**Usage:**
```python
result = await client.call_tool("get_network_topology", {})
```

### 3. `predict_link_health(rx_errors, tx_errors, utilization)`

Runs an AI model to predict overall link health based on telemetry metrics. Uses a PyTorch neural network with GPU acceleration support.

**Maps to NCP functionality:**
- Analyzes real-time telemetry from network devices
- Uses ML model to predict link degradation before failures occur
- Provides actionable health scores for monitoring and alerting
- Integrates with remediation workflows for automated response

**Parameters:**
- `rx_errors` (int): Number of receive errors
- `tx_errors` (int): Number of transmit errors
- `utilization` (float): Link utilization (0.0 to 1.0)

**Returns:**
```json
{
  "health_score": 0.823,
  "status": "healthy",
  "inputs": {
    "rx_errors": 2,
    "tx_errors": 5,
    "utilization": 0.85
  }
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

**GPU Support:**
- Mac: Uses MPS (Metal Performance Shaders) when available
- Linux/Windows: Can be configured to use CUDA for NVIDIA GPUs
- Falls back to CPU if GPU is unavailable

### 4. `validate_build_metadata(build_json_path)`

Validates SONiC or non-SONiC build JSON files by checking for required fields and structure.

**Maps to NCP functionality:**
- Validates build metadata before deployment
- Ensures version, hardware, and feature consistency
- Prevents deployment of incompatible or misconfigured builds
- Supports vendor-agnostic build validation workflows

**Parameters:**
- `build_json_path` (str): Path to the build JSON file (can be relative to `data/builds/`)

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
  "build_json_path": "data/builds/sonic_build.json"
})
```

### 5. `remediate_link(interface)`

Mock closed-loop automation tool that returns recommended remediation action based on interface health analysis.

**Maps to NCP functionality:**
- Analyzes link health from telemetry data
- Determines appropriate remediation action based on device type and issue
- Returns actionable recommendations for automation workflows
- Supports closed-loop automation for network operations

**Parameters:**
- `interface` (str): Interface name (e.g., "Ethernet12", "GigabitEthernet0/1")

**Returns:**
```json
{
  "interface": "Ethernet12",
  "recommended_action": "restart_port",
  "reason": "High error rate detected. Interface restart recommended.",
  "confidence": 0.85,
  "estimated_downtime_seconds": 5,
  "device_type": "SONiC",
  "timestamp": "2024-01-15T10:30:00Z",
  "next_steps": [
    "Review telemetry data",
    "Execute remediation if approved",
    "Monitor interface post-remediation"
  ]
}
```

**Usage:**
```python
result = await client.call_tool("remediate_link", {
  "interface": "Ethernet12"
})
```

### 6. `get_device_status_from_telnet(host, username, password, command)`

Establishes a Telnet session and runs a command on a network device. Connects to SONiC, EdgeCore, Celtica DS4000, NVIDIA SN2700, or other network devices via Telnet and executes CLI commands.

**Maps to NCP functionality:**
- Connects to network devices via Telnet for CLI access
- Executes device commands (show interfaces, show version, show environment)
- Normalizes output across different device vendors
- Supports SONiC, EdgeCore, Celtica DS4000, and NVIDIA SN2700 switches
- In production, integrates with device inventory for automated data collection

**Parameters:**
- `host` (str): Device hostname or IP address
- `username` (str): Telnet username
- `password` (str): Telnet password
- `command` (str): CLI command to execute (e.g., "show version", "show interfaces")

**Returns:**
```json
{
  "success": true,
  "host": "192.168.1.100",
  "command": "show version",
  "output": "SONiC Software Version: SONiC.202311.1...",
  "error": null
}
```

**Usage:**
```python
result = await client.call_tool("get_device_status_from_telnet", {
  "host": "192.168.1.100",
  "username": "admin",
  "password": "password",
  "command": "show version"
})
```

**Error Handling:**
- Connection timeouts are handled gracefully
- Authentication failures return clear error messages
- Invalid parameters are validated before connection attempts

### 7. `get_topology_from_netbox(base_url, token)`

Fetches network topology from NetBox (source of truth). Connects to NetBox's REST API to retrieve devices, interfaces, and links, building a graph representation of the network topology.

**Maps to NCP functionality:**
- Retrieves device inventory from NetBox (source of truth)
- Fetches interface and link information for topology mapping
- Builds unified network graph across all device types
- Supports SONiC, EdgeCore, Celtica DS4000, NVIDIA SN2700, and other devices
- In production, provides real-time topology updates for NCP operations

**Parameters:**
- `base_url` (str): NetBox base URL (e.g., "https://netbox.example.com")
- `token` (str): NetBox API token for authentication

**Returns:**
```json
{
  "success": true,
  "devices": [
    {
      "id": 1,
      "name": "sonic-leaf-01",
      "device_type": "S5248F-ON",
      "manufacturer": "Dell",
      "site": "Data Center A",
      "status": "active",
      "role": "leaf",
      "primary_ip": "192.168.1.100/24"
    }
  ],
  "links": [
    {
      "id": 1,
      "source_device": "sonic-leaf-01",
      "source_interface": "Ethernet12",
      "target_device": "sonic-spine-01",
      "target_interface": "Ethernet1/1",
      "status": "connected",
      "type": "cat6"
    }
  ],
  "statistics": {
    "total_devices": 25,
    "total_interfaces": 150,
    "total_links": 45
  },
  "error": null
}
```

**Usage:**
```python
result = await client.call_tool("get_topology_from_netbox", {
  "base_url": "https://netbox.example.com",
  "token": "your-api-token-here"
})
```

**Error Handling:**
- Authentication failures return clear error messages
- Connection errors are handled with timeout protection
- Invalid API responses are validated and reported
- **Sample Data Fallback**: If no API token is provided or token is invalid, the tool automatically falls back to sample NetBox data from `data/netbox_sample.json` for testing purposes

### 8. `get_device_and_interface_report(netbox_url, netbox_token, telnet_host, telnet_username, telnet_password, telnet_command)`

Combines NetBox device inventory data with Telnet interface information. This tool demonstrates how Aviz NCP agents retrieve live device data from NetBox (source of truth) and combine it with real-time interface data from Telnet connections, mirroring the AI ONE Center workflow.

**Maps to NCP AI ONE Center functionality:**
- Retrieves device inventory from NetBox (source of truth)
- Connects to devices via Telnet to get real-time interface status
- Combines inventory data with live device state
- Validates that devices in NetBox are actually reachable
- In production, used for automated validation and monitoring

**Parameters:**
- `netbox_url` (str, optional): NetBox API URL (defaults to .env NETBOX_URL or https://demo.netbox.dev/api/)
- `netbox_token` (str, optional): NetBox API token (defaults to .env NETBOX_TOKEN)
- `telnet_host` (str, optional): Device hostname/IP (defaults to .env TELNET_HOST)
- `telnet_username` (str, optional): Telnet username (defaults to .env TELNET_USERNAME)
- `telnet_password` (str, optional): Telnet password (defaults to .env TELNET_PASSWORD)
- `telnet_command` (str, optional): CLI command to execute (defaults to "show interfaces status")

**Returns:**
```json
{
  "NetBox_Devices": ["sonic-leaf-01", "nexus-agg-02", "edgecore-switch-03"],
  "Telnet_Output": "Port      Name         Status    Vlan    Duplex  Speed Type...",
  "NetBox_Status": "Success",
  "Telnet_Status": "Success",
  "error": null
}
```

**Usage:**
```python
# Using .env file for credentials
result = await client.call_tool("get_device_and_interface_report", {})

# Or with explicit parameters
result = await client.call_tool("get_device_and_interface_report", {
  "netbox_url": "https://demo.netbox.dev/api/",
  "telnet_host": "192.168.1.100",
  "telnet_username": "admin",
  "telnet_password": "password",
  "telnet_command": "show interfaces status"
})
```

**Error Handling:**
- NetBox connection failures are handled gracefully
- Telnet connection timeouts and authentication errors are reported
- Missing credentials default to .env file values
- Tool returns partial results if one data source fails

### 9. `validate_system_health(netbox_url, netbox_token, elk_endpoint, servicenow_url, zendesk_url)`

Performs comprehensive system health validation similar to Aviz AI ONE Center's QA validation process. Validates all critical system components including NetBox inventory, Syslog/ELK connectivity, ServiceNow and Zendesk integrations, and FlowAnalytics licensing.

**Maps to NCP AI ONE Center functionality:**
- Validates NetBox inventory consistency and device counts
- Checks Syslog/ELK connector health and connectivity
- Verifies ServiceNow integration accessibility
- Validates Zendesk integration status
- Checks FlowAnalytics license availability
- Returns structured summary similar to AI ONE Center reports
- Can be extended to automatically open JIRA tickets on failures

**Parameters:**
- `netbox_url` (str, optional): NetBox instance URL
- `netbox_token` (str, optional): NetBox API token (uses sample data if not provided)
- `elk_endpoint` (str, optional): ELK/Syslog endpoint URL
- `servicenow_url` (str, optional): ServiceNow instance URL
- `zendesk_url` (str, optional): Zendesk API URL

**Returns:**
```json
{
  "NetBox": {
    "status": "Failed",
    "details": "Device count mismatch: found 18, expected 23"
  },
  "Syslog": {
    "status": "Failed",
    "details": "ELK connector crashed intermittently - service unavailable"
  },
  "ServiceNow": {
    "status": "Passed",
    "details": "ServiceNow API accessible"
  },
  "Zendesk": {
    "status": "Passed",
    "details": "Zendesk API accessible"
  },
  "FlowAnalytics": {
    "status": "Not Run",
    "details": "FlowAnalytics license missing - validation skipped",
    "reason": "missing license"
  },
  "Total": {
    "Passed": 2,
    "Failed": 2,
    "NotRun": 1
  }
}
```

**Usage:**
```python
result = await client.call_tool("validate_system_health", {
  "netbox_url": "https://netbox.example.com",
  "netbox_token": "your-token-here",
  "elk_endpoint": "http://elk.example.com:9200"
})
```

**Error Handling:**
- Each component validation is independent and isolated
- Connection failures are handled gracefully
- Missing licenses or data sources return "Not Run" status
- All failures include detailed error messages

## System Health Validation (AI ONE Center Style)

The `validate_system_health()` tool mirrors the validation process used in Aviz AI ONE Center POC. This tool performs comprehensive system-wide validation checks similar to the QA process that identifies common failure points in production environments.

### Common Failure Points Detected

The validation tool checks for typical issues found in AI ONE Center deployments:

1. **NetBox Inventory Issues:**
   - Device count mismatches (e.g., inventory shows 18/23 devices)
   - Missing critical devices
   - Naming inconsistencies
   - Incomplete inventory data

2. **Syslog/ELK Connector Issues:**
   - ELK connector crashing intermittently
   - Connection timeouts
   - Service unavailability

3. **Data Source Integration Issues:**
   - ServiceNow API connectivity problems
   - Zendesk authentication failures
   - Missing or outdated data sources

4. **Licensing Issues:**
   - FlowAnalytics license missing or invalid
   - License expiration

5. **Data Quality Issues:**
   - Inventory Insight showing IP instead of MAC addresses
   - Missing metadata leading to "Not Run" test cases

### Integration with JIRA

The validation tool is designed to be extended with automatic JIRA ticket creation on failures. In production, this would:

- Create JIRA tickets for each failed component
- Include detailed error messages and context
- Assign tickets to appropriate teams
- Track resolution status

**Example Extension:**
```python
# Future enhancement: Automatic JIRA ticket creation
if health_result["Total"]["Failed"] > 0:
    for component, result in health_result.items():
        if result.get("status") == "Failed":
            create_jira_ticket(
                title=f"System Health: {component} Validation Failed",
                description=result.get("details"),
                assignee="ops-team"
            )
```

### Modular Design

Each validation check is implemented as a separate function in `agents/validation_agent.py`:

- `validate_netbox()` - NetBox inventory validation
- `validate_syslog()` - ELK/Syslog connectivity check
- `validate_servicenow()` - ServiceNow integration check
- `validate_zendesk()` - Zendesk integration check
- `validate_flowanalytics()` - FlowAnalytics license check

This modular design allows each sub-check to be replaced with real API connectors as needed, without affecting other validation components.

## Combined Data Source Integration

The `get_device_and_interface_report()` tool demonstrates how Aviz NCP agents combine data from multiple sources to create comprehensive network reports. This workflow is essential for AI ONE Center operations:

### NetBox + Telnet Workflow

1. **NetBox Query**: Retrieve device inventory from source of truth
2. **Telnet Connection**: Connect to devices to get real-time interface status
3. **Data Combination**: Merge inventory data with live device state
4. **Validation**: Verify that devices in NetBox are actually reachable

**Example Use Case:**
```python
# Generate combined report
report = await client.call_tool("get_device_and_interface_report", {})

# Check if devices in NetBox are actually reachable
netbox_devices = report["NetBox_Devices"]
if report["Telnet_Status"] == "Success":
    print(f"Successfully connected to device, validating NetBox inventory...")
    # Compare NetBox devices with actual device state
    validate_device_reachability(netbox_devices)
```

### Environment Variable Configuration

The tool supports loading credentials from a `.env` file for secure credential management:

```bash
# .env file
NETBOX_URL=https://demo.netbox.dev/api/
NETBOX_TOKEN=your-token-here
TELNET_HOST=192.168.1.100
TELNET_USERNAME=admin
TELNET_PASSWORD=password
```

This allows you to:
- Keep credentials out of code and version control
- Switch between environments (dev/staging/prod)
- Share configuration templates without exposing secrets

## Integration with Real Infrastructure

The framework now includes integration tools for connecting to real network devices and infrastructure sources:

### Telnet Integration

The Telnet integration tool enables direct CLI access to network devices. This is essential for Aviz NCP's operations as it allows:

- **Device Discovery**: Execute commands to discover device capabilities and versions
- **Health Checks**: Run diagnostic commands (show version, show environment) to verify device health
- **Configuration Retrieval**: Extract current device configurations for analysis
- **Vendor Agnostic**: Works with SONiC, EdgeCore, Celtica DS4000, NVIDIA SN2700, and other vendors

**Example Workflow:**
```python
# Check device version before deployment
version = await client.call_tool("get_device_status_from_telnet", {
  "host": "switch-01.example.com",
  "username": "admin",
  "password": "secure-password",
  "command": "show version"
})

if version["success"]:
    # Parse version information
    analyze_device_version(version["output"])
```

### NetBox Integration

NetBox serves as Aviz NCP's source of truth for network topology and device inventory. The NetBox integration tool enables:

- **Topology Discovery**: Automatically discover network topology from NetBox
- **Device Inventory**: Retrieve complete device inventory with all metadata
- **Link Mapping**: Understand physical and logical connections between devices
- **Real-time Updates**: Fetch current topology state for NCP operations
- **Sample Data Fallback**: For testing without NetBox access, automatically uses sample data from `data/netbox_sample.json`

**Example Workflow:**
```python
# Fetch topology from NetBox (production)
topology = await client.call_tool("get_topology_from_netbox", {
  "base_url": "https://netbox.production.example.com",
  "token": os.environ["NETBOX_API_TOKEN"]
})

# Or use sample data for testing (automatic fallback)
topology = await client.call_tool("get_topology_from_netbox", {
  "base_url": "https://netbox.example.com",
  "token": "your-api-token-here"  # Will automatically use sample data
})

if topology["success"]:
    # Use topology for NCP operations
    for device in topology["devices"]:
        if device["status"] == "active":
            monitor_device(device["name"])
```

## Running the Agent

### Start the MCP Server

```bash
python mcp_server.py
```

The server will initialize all agents, load the AI model, and wait for requests on stdio. Logs are written to stderr.

### Interactive CLI Agent

```bash
python main_agent.py
```

This launches an interactive conversational interface where you can ask natural language questions:
- "Show me the network topology"
- "List all devices from NetBox"
- "Get device and interface report"
- "What is the port telemetry?"
- "Validate system health"
- "Which VLAN is this device on?"
- "List all interfaces for sonic-leaf-01"

The agent uses an LLM (OpenAI) or pattern matching to parse your queries and map them to appropriate MCP tools, then formats the responses in clear tables and summaries.

**Note:** For LLM support, set `OPENAI_API_KEY` environment variable. Without it, the agent falls back to pattern-based query parsing.

### Test with Client

```bash
python client_test.py
```

The test client demonstrates all nine tools:
1. Port telemetry collection
2. Network topology retrieval
3. Link health prediction
4. Build metadata validation
5. Link remediation recommendations
6. Device status via Telnet
7. Topology from NetBox
8. Device and interface report (NetBox + Telnet combined)
9. System health validation (AI ONE Center style)

### Example Output

```
Starting MCP server...
Connected to MCP server: aviz-ncp-ai-agent v1.0.0

======================================================================
Test 1: Get Port Telemetry
======================================================================
{
  "switch": "sonic-leaf-01",
  "interface": "Ethernet12",
  "rx_bytes": 4567890,
  "tx_bytes": 5678901,
  "rx_errors": 3,
  "tx_errors": 7,
  "utilization": 0.72
}

======================================================================
Test 2: Get Network Topology
======================================================================
Topology: 5 devices, 4 links
  SONiC devices: 3
  Non-SONiC devices: 2

======================================================================
Test 3: Predict Link Health
======================================================================
{
  "health_score": 0.787,
  "status": "healthy",
  "inputs": {
    "rx_errors": 2,
    "tx_errors": 5,
    "utilization": 0.85
  }
}

======================================================================
Test 4: Validate Build Metadata
======================================================================
Valid: true
Device Type: SONiC

======================================================================
Test 5: Remediate Link
======================================================================
Recommended Action: restart_port
Reason: High error rate detected. Interface restart recommended.
Confidence: 0.85

======================================================================
Test 6: Get Device Status from Telnet
======================================================================
Note: This test uses mock credentials. In production, use real device credentials.
Success: Command executed on 192.168.1.100
Command: show version
Output length: 1234 characters

======================================================================
Test 7: Get Topology from NetBox
======================================================================
Note: This test requires NetBox URL and API token. Using example values.
Success: Topology fetched from NetBox
Devices: 25
Interfaces: 150
Links: 45
```

## Real-World Customer Workflows

This framework simulates real NCP customer workflows:

### SONiC Build Validation

Before deploying SONiC builds to production switches, NCP validates build metadata to ensure compatibility:

```python
# Validate SONiC build before deployment
validation = await client.call_tool("validate_build_metadata", {
  "build_json_path": "data/builds/sonic_build.json"
})

if validation["valid"]:
    # Proceed with deployment
    deploy_build()
else:
    # Block deployment and alert
    alert_ops_team(validation["errors"])
```

### Multi-Vendor Telemetry Monitoring

NCP collects telemetry from diverse device types and normalizes it for AI analysis:

```python
# Get unified topology view
topology = await client.call_tool("get_network_topology", {})

# Monitor all devices regardless of vendor
for device in topology["devices"]:
    if device["status"] != "active":
        alert_ops_team(f"Device {device['id']} is down")
```

### Automated Remediation

When AI detects link degradation, NCP can automatically recommend or execute remediation:

```python
# Predict health
health = await client.call_tool("predict_link_health", {
  "rx_errors": 10,
  "tx_errors": 15,
  "utilization": 0.95
})

if health["status"] == "warning":
    # Get remediation recommendation
    remediation = await client.call_tool("remediate_link", {
      "interface": "Ethernet12"
    })
    
    # Execute remediation via Ansible (in production)
    if remediation["confidence"] > 0.8:
        execute_remediation(remediation["recommended_action"])
```

## Project Structure Details

### Agents

Each agent module is self-contained and testable:

- **`agents/telemetry_agent.py`**: Handles network telemetry collection and topology generation
- **`agents/ai_agent.py`**: Contains the PyTorch model and health prediction logic with GPU support
- **`agents/build_agent.py`**: Validates build metadata for SONiC and non-SONiC devices
- **`agents/remediation_agent.py`**: Provides automated remediation recommendations
- **`agents/integration_tools.py`**: Integration tools for Telnet and NetBox connectivity
- **`agents/validation_agent.py`**: System health validation similar to AI ONE Center QA checks

### Utilities

- **`utils/logger.py`**: Provides consistent logging configuration across all modules
- **`utils/file_loader.py`**: Handles JSON file loading with path resolution
- **`utils/topology_builder.py`**: Generates mock network topologies

### Data

- **`data/builds/`**: Sample build JSON files for SONiC, Cisco, and EdgeCore devices

## Error Handling

All tools include comprehensive error handling:

- **Input validation**: Parameters are validated before processing
- **Exception handling**: Try/except blocks prevent crashes
- **Structured errors**: Errors are returned as JSON with clear messages
- **Logging**: All errors are logged for debugging
- **Client safety**: Client never hangs waiting for responses

## Development

### Adding New Tools

1. Create or extend an agent module in `agents/`
2. Import the function in `mcp_server.py`
3. Register it with `@mcp.tool()` decorator
4. Add comprehensive docstring describing NCP functionality mapping
5. Update this README with tool documentation

### Logging

All modules use the centralized logger:

```python
from utils.logger import setup_logger

logger = setup_logger(__name__)
logger.info("Your log message")
```

### Testing Individual Agents

```python
from agents.telemetry_agent import get_network_topology
topology = get_network_topology()
print(topology["statistics"])
```

## Dependencies

Additional dependencies required for integration tools:

```bash
pip install requests
```

The `telnetlib` module is part of Python's standard library, so no additional installation is needed for Telnet support.

## Future Integration

This prototype is designed to evolve into production-ready components:

- **gNMI Integration**: Replace mock telemetry with real gNMI streams from network devices
- **Ansible Integration**: Execute remediation actions via Ansible playbooks
- **Multi-agent Orchestration**: Coordinate multiple specialized agents for complex workflows
- **Real-time Monitoring**: Stream telemetry data for continuous analysis
- **Production Models**: Replace mock models with trained ML models from production data
- **SSH Support**: Add SSH connectivity as an alternative to Telnet for secure device access
- **Enhanced NetBox Integration**: Support for NetBox webhooks and real-time topology updates

## GPU Configuration

The AI agent supports GPU acceleration:

- **Mac**: Uses MPS (Metal Performance Shaders) automatically
- **Linux/Windows with NVIDIA**: Modify `agents/ai_agent.py` to use CUDA:
  ```python
  device = "cuda" if torch.cuda.is_available() else "cpu"
  ```
- **CPU Fallback**: Automatically falls back to CPU if GPU is unavailable

## License

See repository for license information.

## Contributing

This is a prototype for Aviz Networks' NCP platform. For contributions, please follow the project's contribution guidelines.
