"""MCP Server for Aviz NCP AI Agent.

This agent simulates Aviz NCP's AI infrastructure for validating builds,
monitoring multi-vendor telemetry, predicting link health, and automated remediation.

The server orchestrates multiple AI agents that work together to provide
vendor-agnostic network observability, validation, and automation capabilities.
"""
from mcp.server.fastmcp import FastMCP
from utils.logger import setup_logger
from datetime import datetime
from agents.telemetry_agent import get_port_telemetry as _get_port_telemetry, get_network_topology as _get_network_topology
from agents.ai_agent import predict_link_health as _predict_link_health
from agents.build_agent import validate_build_metadata as _validate_build_metadata
from agents.remediation_agent import remediate_link as _remediate_link
from agents.integration_tools import get_device_status_from_telnet as _get_device_status_from_telnet, get_topology_from_netbox as _get_topology_from_netbox, get_device_and_interface_report as _get_device_and_interface_report
from agents.validation_agent import validate_system_health as _validate_system_health
from agents.inventory_agent import (
    get_device_info as _get_device_info,
    list_devices_by_vlan as _list_devices_by_vlan,
    get_vlan_table as _get_vlan_table,
    load_device_inventory,
    load_yaml_inventory,
    load_netbox_inventory,
    merge_inventories,
    group_by,
    detect_mismatches,
    optional_identity_verify
)
from agents.inventory_models import InventorySnapshot, InventoryReport
from utils.renderers import to_table, to_json, to_markdown_report, to_html_report

# Initialize logger
logger = setup_logger(__name__)

# Initialize MCP server
mcp = FastMCP("aviz-ncp-ai-agent")
logger.info("Initializing Aviz NCP AI Agent MCP Server")

# Load device inventory from YAML at startup
try:
    load_device_inventory()
    logger.info("Device inventory loaded successfully")
except Exception as e:
    logger.warning(f"Failed to load device inventory: {e}")
    logger.warning("Device inventory queries will not be available")


# -----------------------------
# 1. TELEMETRY TOOLS
# -----------------------------

@mcp.tool()
def get_port_telemetry() -> dict:
    """
    Simulate SONiC port telemetry metrics.
    
    Maps to Aviz NCP functionality:
    - Collects real-time interface statistics from SONiC switches
    - Normalizes data for consumption by AI/ML models
    - Supports integration with gNMI telemetry streams
    
    Returns:
        Dictionary containing port telemetry data (rx_bytes, tx_bytes, errors, utilization)
    """
    try:
        return _get_port_telemetry()
    except Exception as e:
        logger.error(f"Error collecting port telemetry: {e}")
        return {
            "error": "Telemetry collection failed",
            "message": str(e)
        }


@mcp.tool()
def get_network_topology() -> dict:
    """
    Return a mock network topology with multiple device types.
    
    Simulates a multi-vendor network with SONiC, Cisco, FortiGate, and EdgeCore devices.
    This demonstrates Aviz NCP's vendor-agnostic approach to network management.
    - Normalizes device and link information across vendors
    - Provides unified view of network infrastructure
    - Supports both SONiC (~5%) and non-SONiC devices (~95%)
    Returns:
        Dictionary containing network topology with devices, links, and statistics
    """
    try:
        return _get_network_topology()
    except Exception as e:
        logger.error(f"Error generating network topology: {e}")
        return {
            "error": "Topology generation failed",
            "message": str(e),
            "devices": [],
            "links": [],
            "statistics": {}
        }


# -----------------------------
# 2. AI PREDICTION TOOLS
# -----------------------------

@mcp.tool()
def predict_link_health(rx_errors: int, tx_errors: int, utilization: float) -> dict:
    """
    Run AI model to predict overall link health based on telemetry.
    
    Uses a PyTorch neural network to analyze link metrics and predict health.
    Supports GPU acceleration via MPS (Mac) or CUDA (Linux/Windows).
    
    Maps to Aviz NCP functionality:
    - Analyzes real-time telemetry from network devices
    - Uses ML model to predict link degradation before failures occur
    - Provides actionable health scores for monitoring and alerting
    - Integrates with remediation workflows for automated response
    
    Args:
        rx_errors: Number of receive errors
        tx_errors: Number of transmit errors
        utilization: Link utilization (0.0 to 1.0)
        
    Returns:
        Dictionary containing health_score and status
    """
    try:
        return _predict_link_health(rx_errors, tx_errors, utilization)
    except Exception as e:
        logger.error(f"Error predicting link health: {e}")
        return {
            "error": "Health prediction failed",
            "message": str(e),
            "health_score": None,
            "status": "error"
        }


# -----------------------------
# 3. BUILD VALIDATION TOOLS
# -----------------------------

@mcp.tool()
def validate_build_metadata(build_json_path: str) -> dict:
    """
    Validate SONiC or non-SONiC build JSON files.
    
    Checks build metadata files for required fields and structure.
    Supports both SONiC and non-SONiC device builds with different validation rules.
    
    Maps to Aviz NCP functionality:
    - Validates build metadata before deployment
    - Ensures version, hardware, and feature consistency
    - Prevents deployment of incompatible or misconfigured builds
    - Supports vendor-agnostic build validation workflows
    
    Args:
        build_json_path: Path to the build JSON file (can be relative to data/builds/)
        
    Returns:
        Dictionary containing validation results, errors, and warnings
    """
    try:
        return _validate_build_metadata(build_json_path)
    except Exception as e:
        logger.error(f"Error validating build metadata: {e}")
        return {
            "valid": False,
            "error": "Validation failed",
            "message": str(e),
            "errors": [str(e)],
            "warnings": []
        }


# -----------------------------
# 4. REMEDIATION TOOLS
# -----------------------------

@mcp.tool()
def remediate_link(interface: str) -> dict:
    """
    Mock closed-loop automation tool that returns recommended remediation action.
    
    Analyzes interface health and returns actionable remediation recommendations.
    In production, this would integrate with Ansible or similar automation tools
    to execute remediation actions automatically.
    
    Maps to Aviz NCP functionality:
    - Analyzes link health from telemetry data
    - Determines appropriate remediation action based on device type and issue
    - Returns actionable recommendations for automation workflows
    - Supports closed-loop automation for network operations
    
    Args:
        interface: Interface name (e.g., "Ethernet12", "GigabitEthernet0/1")
        
    Returns:
        Dictionary containing recommended action, reason, and confidence
    """
    try:
        return _remediate_link(interface)
    except Exception as e:
        logger.error(f"Error generating remediation recommendation: {e}")
        return {
            "error": "Remediation analysis failed",
            "message": str(e),
            "interface": interface,
            "recommended_action": None
        }


# -----------------------------
# 5. INTEGRATION TOOLS
# -----------------------------

@mcp.tool()
def get_device_status_from_telnet(host: str, username: str, password: str, command: str) -> dict:
    """
    Establish a Telnet session and run a command on a network device.
    
    Connects to SONiC, EdgeCore, Celtica DS4000, NVIDIA SN2700, or other network
    devices via Telnet and executes CLI commands like show interfaces, show version,
    and show environment.
    
    Maps to Aviz NCP functionality:
    - Connects to network devices via Telnet for CLI access
    - Executes device commands (show interfaces, show version, show environment)
    - Normalizes output across different device vendors
    - Supports SONiC, EdgeCore, Celtica DS4000, and NVIDIA SN2700 switches
    - In production, integrates with device inventory for automated data collection
    
    Args:
        host: Device hostname or IP address
        username: Telnet username
        password: Telnet password
        command: CLI command to execute (e.g., "show version", "show interfaces")
        
    Returns:
        Dictionary containing success status, command output, and error information
    """
    try:
        return _get_device_status_from_telnet(host, username, password, command)
    except Exception as e:
        logger.error(f"Error executing Telnet command: {e}")
        return {
            "success": False,
            "host": host,
            "command": command,
            "output": "",
            "error": f"Telnet execution failed: {str(e)}"
        }


@mcp.tool()
def get_topology_from_netbox(base_url: str, token: str) -> dict:
    """
    Fetch network topology from NetBox (source of truth).
    
    Connects to NetBox's REST API to retrieve devices, interfaces, and links,
    building a graph representation of the network topology.
    
    Maps to Aviz NCP functionality:
    - Retrieves device inventory from NetBox (source of truth)
    - Fetches interface and link information for topology mapping
    - Builds unified network graph across all device types
    - Supports SONiC, EdgeCore, Celtica DS4000, NVIDIA SN2700, and other devices
    - In production, provides real-time topology updates for NCP operations
    
    Args:
        base_url: NetBox base URL (e.g., "https://netbox.example.com")
        token: NetBox API token for authentication
        
    Returns:
        Dictionary containing devices (nodes), links (edges), and topology statistics
    """
    try:
        return _get_topology_from_netbox(base_url, token)
    except Exception as e:
        logger.error(f"Error fetching topology from NetBox: {e}")
        return {
            "success": False,
            "devices": [],
            "links": [],
            "statistics": {
                "total_devices": 0,
                "total_interfaces": 0,
                "total_links": 0
            },
            "error": f"NetBox fetch failed: {str(e)}"
        }


# -----------------------------
# 6. COMBINED DATA SOURCE TOOLS
# -----------------------------

@mcp.tool()
def get_device_and_interface_report(
    netbox_url: str = "",
    netbox_token: str = "",
    telnet_host: str = "",
    telnet_username: str = "",
    telnet_password: str = "",
    telnet_command: str = "show interfaces status"
) -> dict:
    """
    Combine NetBox device data with Telnet interface information.
    
    This tool demonstrates how Aviz NCP agents can retrieve live device data
    from NetBox (source of truth) and combine it with real-time interface data
    from Telnet connections. This mirrors the AI ONE Center workflow of
    validating inventory against actual device state.
    
    Maps to Aviz NCP AI ONE Center functionality:
    - Retrieves device inventory from NetBox (source of truth)
    - Connects to devices via Telnet to get real-time interface status
    - Combines inventory data with live device state
    - Validates that devices in NetBox are actually reachable
    - In production, this would be used for automated validation and monitoring
    
    Integration Points for Future Enhancement:
    - FastDI Integration: Replace Telnet with FastDI API calls for real-time
      device state retrieval. FastDI provides structured telemetry data that
      can be directly consumed without parsing CLI output.
    - ELK Integration: Enhance NetBox device list with ELK log analysis to
      identify devices with recent errors or anomalies. This would add a
      "health_score" field based on syslog patterns.
    - gNMI Integration: Replace Telnet interface queries with gNMI Subscribe
      for streaming telemetry. This provides real-time interface counters
      and state information.
    
    Args:
        netbox_url: NetBox API URL (optional, defaults to .env NETBOX_URL or demo.netbox.dev)
        netbox_token: NetBox API token (optional, defaults to .env NETBOX_TOKEN)
        telnet_host: Device hostname/IP (optional, defaults to .env TELNET_HOST)
        telnet_username: Telnet username (optional, defaults to .env TELNET_USERNAME)
        telnet_password: Telnet password (optional, defaults to .env TELNET_PASSWORD)
        telnet_command: CLI command to execute (defaults to "show interfaces status")
        
    Returns:
        Dictionary containing:
        - NetBox_Devices: List of device names from NetBox inventory
        - Telnet_Output: First 500 characters of Telnet command output
        - NetBox_Status: "Success", "Failed", or "Not Run"
        - Telnet_Status: "Success", "Failed", "Skipped", or "Not Run"
        - error: Error message if any operation failed
        
    Error Handling:
        - NetBox connection failures are handled gracefully and reported
        - Telnet connection timeouts and authentication errors are caught
        - Missing credentials default to .env file values
        - Tool returns partial results if one data source fails
    """
    try:
        return _get_device_and_interface_report(
            netbox_url=netbox_url if netbox_url else None,
            netbox_token=netbox_token if netbox_token else None,
            telnet_host=telnet_host if telnet_host else None,
            telnet_username=telnet_username if telnet_username else None,
            telnet_password=telnet_password if telnet_password else None,
            telnet_command=telnet_command
        )
    except Exception as e:
        logger.error(f"Error generating device and interface report: {e}", exc_info=True)
        return {
            "error": "Report generation failed",
            "message": str(e),
            "NetBox_Devices": [],
            "Telnet_Output": "",
            "NetBox_Status": "Failed",
            "Telnet_Status": "Failed"
        }


# -----------------------------
# 7. DEVICE INVENTORY TOOLS (YAML-based)
# -----------------------------

@mcp.tool()
def get_device_info(device_name: str = "", query_type: str = "") -> dict:
    """
    Get device information from YAML inventory.
    
    This tool queries the device inventory loaded from devices.yaml file.
    It supports querying by device name, role, vendor, OS type, or returning all devices.
    
    Maps to Aviz NCP functionality:
    - Provides device inventory lookup from YAML source of truth
    - Returns device metadata including IP, VLANs, role, vendor, OS
    - Supports filtering by various criteria (role, vendor, OS)
    - In production, this would integrate with NetBox and Telnet for real-time data
    
    Args:
        device_name: Name of the device to query (optional, returns all if not provided)
        query_type: Type of query - "all", "sonic", "by_role", "by_vendor", "by_os" (optional)
        
    Returns:
        Dictionary containing device information:
        - device: Single device info if device_name provided
        - devices: List of devices matching query
        - count: Number of devices returned
        - grouped_by_role/vendor/os: Grouped results if query_type specified
        
    Example:
        get_device_info(device_name="sonic-leaf-01") returns:
        {
            "device": {
                "name": "sonic-leaf-01",
                "ip": "10.20.11.207",
                "vendor": "EdgeCore",
                "os": "SONiC",
                "role": "leaf",
                "vlans": [{"id": 101, "name": "management"}, ...]
            },
            "devices": [...],
            "count": 1
        }
    """
    try:
        return _get_device_info(device_name=device_name if device_name else None, query_type=query_type if query_type else None)
    except Exception as e:
        logger.error(f"Error getting device info: {e}", exc_info=True)
        return {
            "error": "Failed to get device information",
            "message": str(e),
            "success": False,
            "devices": []
        }


@mcp.tool()
def list_devices_by_vlan(vlan_id: int) -> dict:
    """
    Find all devices connected to a given VLAN ID.
    
    This tool searches the device inventory for all devices that have a specific
    VLAN configured and returns their information along with VLAN details.
    
    Maps to Aviz NCP functionality:
    - Provides VLAN-to-device mapping from inventory
    - Returns device list with VLAN information
    - Supports network topology queries by VLAN
    - In production, this would cross-reference with NetBox and Telnet data
    
    Args:
        vlan_id: VLAN ID to search for (integer)
        
    Returns:
        Dictionary containing:
        - vlan_id: The VLAN ID searched
        - devices: List of devices with that VLAN (each includes name, ip, vendor, os, role, vlan)
        - count: Number of devices found
        
    Example:
        list_devices_by_vlan(vlan_id=103) returns:
        {
            "vlan_id": 103,
            "devices": [
                {
                    "name": "sonic-leaf-01",
                    "ip": "10.20.11.207",
                    "vendor": "EdgeCore",
                    "os": "SONiC",
                    "role": "leaf",
                    "vlan": {"id": 103, "name": "production"}
                },
                ...
            ],
            "count": 2
        }
    """
    try:
        return _list_devices_by_vlan(vlan_id)
    except Exception as e:
        logger.error(f"Error listing devices by VLAN: {e}", exc_info=True)
        return {
            "error": "Failed to list devices by VLAN",
            "message": str(e),
            "vlan_id": vlan_id,
            "devices": [],
            "count": 0
        }


@mcp.tool()
def get_vlan_table() -> dict:
    """
    Generate a VLAN table showing all VLANs and the devices on each VLAN.
    
    This tool creates a comprehensive VLAN-to-device mapping table from the
    device inventory, showing which devices are configured on each VLAN.
    
    Maps to Aviz NCP functionality:
    - Provides complete VLAN topology from inventory
    - Shows device distribution across VLANs
    - Supports network planning and troubleshooting
    - In production, this would integrate with NetBox topology data
    
    Returns:
        Dictionary containing:
        - vlan_table: List of VLAN entries, each with:
          - vlan_id: VLAN ID
          - vlan_name: VLAN name
          - devices: List of devices on this VLAN
        - total_vlans: Total number of unique VLANs
        - total_devices: Total number of devices in inventory
        
    Example:
        get_vlan_table() returns:
        {
            "vlan_table": [
                {
                    "vlan_id": 101,
                    "vlan_name": "management",
                    "devices": [
                        {"name": "sonic-leaf-01", "ip": "10.20.11.207", "role": "leaf"},
                        ...
                    ]
                },
                ...
            ],
            "total_vlans": 5,
            "total_devices": 5
        }
    """
    try:
        return _get_vlan_table()
    except Exception as e:
        logger.error(f"Error getting VLAN table: {e}", exc_info=True)
        return {
            "error": "Failed to get VLAN table",
            "message": str(e),
            "vlan_table": [],
            "total_vlans": 0,
            "total_devices": 0
        }


# -----------------------------
# 8. SYSTEM HEALTH VALIDATION TOOLS
# -----------------------------

@mcp.tool()
def validate_system_health(
    netbox_url: str = "https://netbox.example.com",
    netbox_token: str = "",
    elk_endpoint: str = "http://elk.example.com:9200",
    servicenow_url: str = "https://example.service-now.com",
    zendesk_url: str = "https://example.zendesk.com/api/v2"
) -> dict:
    """
    Perform comprehensive system health validation.
    
    This tool mirrors the AI ONE Center's QA validation process by checking
    all critical system components for health and consistency.
    
    Maps to Aviz NCP AI ONE Center functionality:
    - Validates NetBox inventory consistency and device counts
    - Checks Syslog/ELK connector health and connectivity
    - Verifies ServiceNow integration accessibility
    - Validates Zendesk integration status
    - Checks FlowAnalytics license availability
    - Returns structured summary similar to AI ONE Center reports
    - Can be extended to automatically open JIRA tickets on failures
    
    Args:
        netbox_url: NetBox instance URL (optional, defaults to example URL)
        netbox_token: NetBox API token (optional, uses sample data if not provided)
        elk_endpoint: ELK/Syslog endpoint URL (optional)
        servicenow_url: ServiceNow instance URL (optional)
        zendesk_url: Zendesk API URL (optional)
        
    Returns:
        Dictionary containing validation results for each component with status
        (Passed/Failed/Not Run) and details, plus a Total summary
    """
    try:
        return _validate_system_health(
            netbox_url=netbox_url,
            netbox_token=netbox_token,
            elk_endpoint=elk_endpoint,
            servicenow_url=servicenow_url,
            zendesk_url=zendesk_url
        )
    except Exception as e:
        logger.error(f"Error performing system health validation: {e}")
        return {
            "error": "System health validation failed",
            "message": str(e),
            "Total": {"Passed": 0, "Failed": 1, "NotRun": 0}
        }


# -----------------------------
# 8. PRODUCTION INVENTORY INSIGHT TOOLS
# -----------------------------

@mcp.tool()
def inventory_list_devices(
    filter_by: str = "",
    value: str = "",
    format: str = "table"
) -> dict:
    """
    List devices from merged inventory (YAML + NetBox) with optional filtering.
    
    This tool provides a unified view of devices from both YAML and NetBox sources,
    with support for filtering and multiple output formats.
    
    Args:
        filter_by: Filter criteria - "vendor", "role", "region", "os", or "vlan_id" (optional)
        value: Filter value to match (optional)
        format: Output format - "table", "json", or "markdown" (default: "table")
        
    Returns:
        Dictionary containing:
        - content: List with text content (table or markdown) or JSON content
        - format: Format used
        - device_count: Number of devices returned
    """
    try:
        # Load and merge inventories
        yaml_snapshot = load_yaml_inventory()
        netbox_snapshot = load_netbox_inventory()
        merged_snapshot = merge_inventories(yaml_snapshot, netbox_snapshot)
        
        devices = merged_snapshot.devices
        
        # Apply filter if specified
        if filter_by and value:
            if filter_by == "vlan_id":
                vlan_id = int(value)
                devices = [d for d in devices if any(v.id == vlan_id for v in d.vlans)]
            else:
                devices = [d for d in devices if str(getattr(d, filter_by, "")).lower() == value.lower()]
        
        # Render in requested format
        if format == "json":
            # Return JSON in json block for JSON format
            json_data = [d.to_dict() for d in devices]
            content = [{"type": "json", "json": json_data}]
        elif format == "markdown":
            from utils.renderers import to_markdown_report
            from agents.inventory_models import InventoryReport
            report = InventoryReport(passed=len(devices), groups={})
            markdown = to_markdown_report(merged_snapshot, report, include_mismatches=False)
            content = [{"type": "text", "text": markdown}]
        else:  # table
            table = to_table(devices)
            content = [{"type": "text", "text": table}]
        
        return {
            "content": content,
            "format": format,
            "device_count": len(devices)
        }
    except Exception as e:
        logger.error(f"Error listing devices: {e}", exc_info=True)
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "format": format,
            "device_count": 0,
            "error": str(e)
        }


@mcp.tool()
def inventory_summary(format: str = "table") -> dict:
    """
    Generate inventory summary with counts by vendor, role, region, and OS.
    
    This tool provides a high-level overview of the inventory with statistics
    grouped by various device attributes.
    
    Args:
        format: Output format - "table", "json", or "markdown" (default: "table")
        
    Returns:
        Dictionary containing:
        - content: List with text content (table or markdown) or JSON content
        - format: Format used
        - totals: Summary statistics
    """
    try:
        # Load and merge inventories
        yaml_snapshot = load_yaml_inventory()
        netbox_snapshot = load_netbox_inventory()
        merged_snapshot = merge_inventories(yaml_snapshot, netbox_snapshot)
        
        # Generate groupings
        vendor_groups = group_by(merged_snapshot, "vendor")
        role_groups = group_by(merged_snapshot, "role")
        os_groups = group_by(merged_snapshot, "os")
        region_groups = group_by(merged_snapshot, "region")
        
        totals = {
            "total_devices": len(merged_snapshot.devices),
            "by_vendor": {k: len(v) for k, v in vendor_groups.items()},
            "by_role": {k: len(v) for k, v in role_groups.items()},
            "by_os": {k: len(v) for k, v in os_groups.items()},
            "by_region": {k: len(v) for k, v in region_groups.items()}
        }
        
        # Render in requested format
        if format == "json":
            # Return JSON in json block for JSON format
            content = [{"type": "json", "json": totals}]
        elif format == "markdown":
            markdown_lines = [
                "# Inventory Summary",
                "",
                f"**Total Devices:** {totals['total_devices']}",
                "",
                "## By Vendor",
                ""
            ]
            for vendor, count in totals["by_vendor"].items():
                markdown_lines.append(f"- {vendor}: {count}")
            markdown_lines.extend(["", "## By Role", ""])
            for role, count in totals["by_role"].items():
                markdown_lines.append(f"- {role}: {count}")
            markdown_lines.extend(["", "## By OS", ""])
            for os_type, count in totals["by_os"].items():
                markdown_lines.append(f"- {os_type}: {count}")
            content = [{"type": "text", "text": "\n".join(markdown_lines)}]
        else:  # table
            table_data = []
            table_data.append(["Total Devices", totals["total_devices"], "", ""])
            table_data.append(["", "", "", ""])
            table_data.append(["Vendor", "Count", "Role", "Count"])
            max_len = max(len(totals["by_vendor"]), len(totals["by_role"]))
            vendors = list(totals["by_vendor"].items())
            roles = list(totals["by_role"].items())
            for i in range(max_len):
                vendor_info = vendors[i] if i < len(vendors) else ("", "")
                role_info = roles[i] if i < len(roles) else ("", "")
                table_data.append([vendor_info[0], vendor_info[1], role_info[0], role_info[1]])
            
            try:
                from tabulate import tabulate
                table = tabulate(table_data, headers=["Category", "Count", "Category", "Count"], tablefmt="grid")
            except ImportError:
                table = "\n".join([" | ".join(str(cell) for cell in row) for row in table_data])
            content = [{"type": "text", "text": table}]
        
        return {
            "content": content,
            "format": format,
            "totals": totals
        }
    except Exception as e:
        logger.error(f"Error generating inventory summary: {e}", exc_info=True)
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "format": format,
            "totals": {},
            "error": str(e)
        }


@mcp.tool()
def inventory_mismatches(
    run_identity_check: bool = False,
    format: str = "table"
) -> dict:
    """
    Detect and report inventory mismatches between YAML and NetBox sources.
    
    This tool compares YAML and NetBox inventories to identify discrepancies
    such as missing devices, role mismatches, vendor mismatches, etc.
    Optionally performs identity verification via SSH/Telnet.
    
    Args:
        run_identity_check: Whether to run SSH/Telnet identity verification (default: False)
        format: Output format - "table", "json", or "markdown" (default: "table")
        
    Returns:
        Dictionary containing:
        - content: List with text content (table or markdown) or JSON content
        - format: Format used
        - mismatch_count: Number of mismatches found
        - mismatches: List of mismatch details
    """
    try:
        # Load inventories
        yaml_snapshot = load_yaml_inventory()
        netbox_snapshot = load_netbox_inventory()
        
        # Detect mismatches
        mismatches = detect_mismatches(yaml_snapshot, netbox_snapshot)
        
        # Optionally run identity verification
        if run_identity_check:
            merged_snapshot = merge_inventories(yaml_snapshot, netbox_snapshot)
            identity_mismatches = optional_identity_verify(merged_snapshot.devices, enabled=True)
            mismatches.extend(identity_mismatches)
        
        # Render in requested format
        if format == "json":
            # Return JSON in json block for JSON format
            mismatch_dicts = [m.to_dict() for m in mismatches]
            content = [{"type": "json", "json": mismatch_dicts}]
        elif format == "markdown":
            markdown_lines = [
                "# Inventory Mismatches",
                "",
                f"**Total Mismatches:** {len(mismatches)}",
                "",
                "| Device | Category | Expected | Observed | Details |",
                "|--------|----------|----------|----------|---------|"
            ]
            for mismatch in mismatches:
                details = mismatch.details or ""
                markdown_lines.append(
                    f"| {mismatch.device_name} | {mismatch.category} | "
                    f"{mismatch.expected} | {mismatch.observed} | {details} |"
                )
            content = [{"type": "text", "text": "\n".join(markdown_lines)}]
        else:  # table
            try:
                from tabulate import tabulate
                table_data = [[
                    m.device_name,
                    m.category,
                    str(m.expected),
                    str(m.observed),
                    (m.details or "")[:50]
                ] for m in mismatches]
                table = tabulate(table_data, headers=["Device", "Category", "Expected", "Observed", "Details"], tablefmt="grid")
            except ImportError:
                table = "\n".join([" | ".join(row) for row in table_data])
            content = [{"type": "text", "text": table}]
        
        return {
            "content": content,
            "format": format,
            "mismatch_count": len(mismatches),
            "mismatches": [m.to_dict() for m in mismatches]
        }
    except Exception as e:
        logger.error(f"Error detecting mismatches: {e}", exc_info=True)
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "format": format,
            "mismatch_count": 0,
            "mismatches": [],
            "error": str(e)
        }


@mcp.tool()
def inventory_report(
    export: str = "none"
) -> dict:
    """
    Generate a consolidated inventory report with snapshot stats, groupings, and mismatches.
    
    This tool creates a comprehensive report combining inventory data from YAML and NetBox,
    including validation results, device groupings, and any detected mismatches.
    Can export the report in Markdown, HTML, or JSON formats.
    
    Args:
        export: Export format - "none", "md", "html", or "json" (default: "none")
        
    Returns:
        Dictionary containing:
        - summary: Short summary of the report
        - file_path: Path to exported file if export != "none"
        - device_count: Total number of devices
        - mismatch_count: Number of mismatches found
        - report_data: Full report data structure
    """
    try:
        # Load and merge inventories
        yaml_snapshot = load_yaml_inventory()
        netbox_snapshot = load_netbox_inventory()
        merged_snapshot = merge_inventories(yaml_snapshot, netbox_snapshot)
        
        # Detect mismatches
        mismatches = detect_mismatches(yaml_snapshot, netbox_snapshot)
        
        # Generate groupings
        vendor_groups = group_by(merged_snapshot, "vendor")
        role_groups = group_by(merged_snapshot, "role")
        os_groups = group_by(merged_snapshot, "os")
        region_groups = group_by(merged_snapshot, "region")
        
        # Create report
        report = InventoryReport(
            passed=len(merged_snapshot.devices) - len(mismatches),
            failed=len(mismatches),
            not_run=0,
            mismatches=mismatches,
            groups={
                "vendor": {k: len(v) for k, v in vendor_groups.items()},
                "role": {k: len(v) for k, v in role_groups.items()},
                "os": {k: len(v) for k, v in os_groups.items()},
                "region": {k: len(v) for k, v in region_groups.items()}
            }
        )
        
        # Generate summary
        summary = (
            f"Inventory report: {len(merged_snapshot.devices)} devices, "
            f"{len(mismatches)} mismatches, "
            f"{report.passed} passed validation"
        )
        
        # Export if requested
        file_path = None
        if export != "none":
            from pathlib import Path
            artifacts_dir = Path("artifacts")
            artifacts_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if export == "md":
                markdown = to_markdown_report(merged_snapshot, report)
                file_path = artifacts_dir / f"inventory_report_{timestamp}.md"
                with open(file_path, 'w') as f:
                    f.write(markdown)
            elif export == "html":
                markdown = to_markdown_report(merged_snapshot, report)
                html = to_html_report(markdown, title="Inventory Report")
                file_path = artifacts_dir / f"inventory_report_{timestamp}.html"
                with open(file_path, 'w') as f:
                    f.write(html)
            elif export == "json":
                report_data = {
                    "snapshot": merged_snapshot.to_dict(),
                    "report": report.to_dict()
                }
                file_path = artifacts_dir / f"inventory_report_{timestamp}.json"
                with open(file_path, 'w') as f:
                    f.write(to_json(report_data))
        
        return {
            "summary": summary,
            "file_path": str(file_path) if file_path else None,
            "device_count": len(merged_snapshot.devices),
            "mismatch_count": len(mismatches),
            "report_data": {
                "snapshot": merged_snapshot.to_dict(),
                "report": report.to_dict()
            }
        }
    except Exception as e:
        logger.error(f"Error generating inventory report: {e}", exc_info=True)
        return {
            "summary": f"Error generating report: {str(e)}",
            "file_path": None,
            "device_count": 0,
            "mismatch_count": 0,
            "report_data": {},
            "error": str(e)
        }


# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    logger.info("Running Aviz NCP AI Agent MCP Server")
    logger.info("Available tools:")
    logger.info("  1. get_port_telemetry - Collect SONiC port telemetry")
    logger.info("  2. get_network_topology - Get multi-vendor network topology")
    logger.info("  3. predict_link_health - AI-based link health prediction")
    logger.info("  4. validate_build_metadata - Validate build JSON files")
    logger.info("  5. remediate_link - Automated link remediation recommendations")
    logger.info("  6. get_device_status_from_telnet - Execute commands via Telnet")
    logger.info("  7. get_topology_from_netbox - Fetch topology from NetBox")
    logger.info("  8. get_device_and_interface_report - Combined NetBox + Telnet report")
    logger.info("  9. get_device_info - Query device inventory from YAML")
    logger.info("  10. list_devices_by_vlan - Find devices by VLAN ID")
    logger.info("  11. get_vlan_table - Generate VLAN-to-device mapping table")
    logger.info("  12. validate_system_health - System-wide health validation (AI ONE Center)")
    logger.info("Waiting for requests on stdio...")
    
    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error in MCP server: {e}")
        raise

