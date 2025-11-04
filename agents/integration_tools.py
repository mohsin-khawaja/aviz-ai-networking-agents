"""Integration tools for connecting to real network devices and infrastructure.

This module provides tools for integrating with Telnet-based device CLIs
and NetBox (source of truth) for topology and inventory management.
"""
import json
import time
import os
import requests
from pathlib import Path
from typing import Dict, Optional, List
from utils.logger import setup_logger

# Handle telnetlib import - deprecated and removed in Python 3.12+
try:
    import telnetlib
    TELNETLIB_AVAILABLE = True
except ImportError:
    # telnetlib removed in Python 3.12+
    TELNETLIB_AVAILABLE = False
    telnetlib = None  # Set to None so code doesn't break

logger = setup_logger(__name__)

# Log warning after logger is available
if not TELNETLIB_AVAILABLE:
    logger.warning("telnetlib not available (removed in Python 3.12+). Telnet features will be disabled.")
    logger.warning("To enable Telnet: pip install telnetlib3")

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.debug("Loaded environment variables from .env file")
except ImportError:
    # dotenv not installed, continue without it
    logger.debug("python-dotenv not installed, skipping .env file loading")


def get_device_status_from_telnet(
    host: str,
    username: str,
    password: str,
    command: str
) -> dict:
    """
    Establish a Telnet session and run a command on a network device.
    
    This tool connects to SONiC, EdgeCore, Celtica DS4000, NVIDIA SN2700,
    or other network devices via Telnet and executes CLI commands.
    
    Note: telnetlib was removed in Python 3.12+. For Python 3.12+, install
    telnetlib3: pip install telnetlib3
    
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
        Dictionary containing:
        - success: Boolean indicating if command executed successfully
        - host: Device hostname/IP
        - command: Command that was executed
        - output: Command output (text)
        - error: Error message if execution failed
    """
    if not TELNETLIB_AVAILABLE:
        return {
            "success": False,
            "host": host,
            "command": command,
            "output": "",
            "error": "Telnet library not available. telnetlib was removed in Python 3.12+. Install telnetlib3: pip install telnetlib3"
        }
    logger.info(f"Connecting to device via Telnet: {host}, command: {command}")
    
    result = {
        "success": False,
        "host": host,
        "command": command,
        "output": "",
        "error": None
    }
    
    if not host or not isinstance(host, str):
        result["error"] = "Invalid host parameter"
        logger.error("Invalid host parameter provided")
        return result
    
    if not command or not isinstance(command, str):
        result["error"] = "Invalid command parameter"
        logger.error("Invalid command parameter provided")
        return result
    
    try:
        # Establish Telnet connection
        logger.debug(f"Attempting Telnet connection to {host}")
        tn = telnetlib.Telnet(host, timeout=10)
        
        # Wait for login prompt and send credentials
        if username:
            tn.read_until(b"login: ", timeout=5)
            tn.write(username.encode('ascii') + b"\n")
        
        if password:
            tn.read_until(b"Password: ", timeout=5)
            tn.write(password.encode('ascii') + b"\n")
        
        # Wait for command prompt (common patterns)
        time.sleep(1)
        tn.read_until(b">", timeout=5)
        tn.read_until(b"#", timeout=5)
        
        # Execute command
        logger.debug(f"Executing command: {command}")
        tn.write(command.encode('ascii') + b"\n")
        
        # Read output
        time.sleep(2)
        output = tn.read_until(b"#", timeout=10).decode('ascii', errors='ignore')
        
        # Clean up output (remove command echo and prompt)
        lines = output.split('\n')
        # Remove command echo and prompt lines
        cleaned_lines = []
        skip_next = False
        for i, line in enumerate(lines):
            if skip_next:
                skip_next = False
                continue
            if command in line and i == 0:
                continue  # Skip command echo
            if line.strip().endswith('#') or line.strip().endswith('>'):
                continue  # Skip prompt
            cleaned_lines.append(line)
        
        output_clean = '\n'.join(cleaned_lines).strip()
        
        tn.close()
        
        result["success"] = True
        result["output"] = output_clean
        logger.info(f"Successfully executed command on {host}")
        logger.debug(f"Command output length: {len(output_clean)} characters")
        
    except telnetlib.socket.timeout:
        result["error"] = "Connection timeout"
        logger.error(f"Telnet connection timeout to {host}")
    except ConnectionRefusedError:
        result["error"] = "Connection refused - device may be unreachable or Telnet disabled"
        logger.error(f"Connection refused to {host}")
    except Exception as e:
        result["error"] = f"Telnet error: {str(e)}"
        logger.error(f"Error executing Telnet command on {host}: {e}")
    
    return result


def get_topology_from_netbox(base_url: str, token: str) -> dict:
    """
    Fetch network topology from NetBox (source of truth).
    
    This tool connects to NetBox's REST API to retrieve devices, interfaces,
    and links, building a graph representation of the network topology.
    
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
        Dictionary containing:
        - success: Boolean indicating if topology fetch succeeded
        - devices: List of devices (nodes)
        - links: List of links (edges)
        - statistics: Topology statistics
        - error: Error message if fetch failed
    """
    logger.info(f"Fetching topology from NetBox: {base_url}")
    
    result = {
        "success": False,
        "devices": [],
        "links": [],
        "statistics": {
            "total_devices": 0,
            "total_interfaces": 0,
            "total_links": 0
        },
        "error": None
    }
    
    if not base_url or not isinstance(base_url, str):
        result["error"] = "Invalid base_url parameter"
        logger.error("Invalid base_url parameter provided")
        return result
    
    # Check if token is provided or if we should use sample data
    use_sample_data = False
    if not token or token == "your-api-token-here" or token == "":
        logger.info("No valid NetBox token provided, attempting to use sample data")
        use_sample_data = True
    
    if use_sample_data:
        # Try to load sample NetBox data from local file
        sample_data_path = Path(__file__).parent.parent / "data" / "netbox_sample.json"
        if sample_data_path.exists():
            logger.info(f"Loading sample NetBox data from {sample_data_path}")
            try:
                with open(sample_data_path, 'r') as f:
                    sample_data = json.load(f)
                result["success"] = True
                result["devices"] = sample_data.get("devices", [])
                result["links"] = sample_data.get("links", [])
                result["statistics"] = sample_data.get("statistics", {
                    "total_devices": len(sample_data.get("devices", [])),
                    "total_interfaces": 0,
                    "total_links": len(sample_data.get("links", []))
                })
                result["note"] = "Using sample data - NetBox API not accessible"
                logger.info(f"Loaded sample topology: {len(result['devices'])} devices, {len(result['links'])} links")
                return result
            except Exception as e:
                logger.warning(f"Failed to load sample data: {e}")
                result["error"] = f"No NetBox token provided and sample data unavailable: {str(e)}"
                return result
        else:
            result["error"] = "No NetBox token provided and sample data file not found"
            logger.error("No token and sample data file missing")
            return result
    
    # Clean up base_url (remove trailing slash)
    base_url = base_url.rstrip('/')
    
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    try:
        # Fetch devices
        logger.debug("Fetching devices from NetBox")
        devices_url = f"{base_url}/api/dcim/devices/"
        devices_response = requests.get(devices_url, headers=headers, timeout=10)
        devices_response.raise_for_status()
        devices_data = devices_response.json()
        
        devices_list = []
        for device in devices_data.get("results", []):
            device_info = {
                "id": device.get("id"),
                "name": device.get("name"),
                "device_type": device.get("device_type", {}).get("model"),
                "manufacturer": device.get("device_type", {}).get("manufacturer", {}).get("name"),
                "site": device.get("site", {}).get("name"),
                "status": device.get("status", {}).get("value"),
                "role": device.get("device_role", {}).get("name"),
                "primary_ip": device.get("primary_ip", {}).get("address") if device.get("primary_ip") else None
            }
            devices_list.append(device_info)
        
        # Fetch interfaces for each device
        logger.debug("Fetching interfaces from NetBox")
        interfaces_url = f"{base_url}/api/dcim/interfaces/"
        interfaces_response = requests.get(interfaces_url, headers=headers, timeout=10, params={"limit": 1000})
        interfaces_response.raise_for_status()
        interfaces_data = interfaces_response.json()
        
        # Fetch cables/links
        logger.debug("Fetching cables/links from NetBox")
        cables_url = f"{base_url}/api/dcim/cables/"
        cables_response = requests.get(cables_url, headers=headers, timeout=10)
        cables_response.raise_for_status()
        cables_data = cables_response.json()
        
        # Build links from cables
        links_list = []
        for cable in cables_data.get("results", []):
            term_a = cable.get("terminations", [{}])[0] if cable.get("terminations") else {}
            term_b = cable.get("terminations", [{}])[1] if len(cable.get("terminations", [])) > 1 else {}
            
            if term_a and term_b:
                link = {
                    "id": cable.get("id"),
                    "source_device": term_a.get("device", {}).get("name") if isinstance(term_a.get("device"), dict) else None,
                    "source_interface": term_a.get("interface", {}).get("name") if isinstance(term_a.get("interface"), dict) else None,
                    "target_device": term_b.get("device", {}).get("name") if isinstance(term_b.get("device"), dict) else None,
                    "target_interface": term_b.get("interface", {}).get("name") if isinstance(term_b.get("interface"), dict) else None,
                    "status": cable.get("status", {}).get("value"),
                    "type": cable.get("type", {}).get("value")
                }
                links_list.append(link)
        
        # Calculate statistics
        total_interfaces = len(interfaces_data.get("results", []))
        
        result["success"] = True
        result["devices"] = devices_list
        result["links"] = links_list
        result["statistics"] = {
            "total_devices": len(devices_list),
            "total_interfaces": total_interfaces,
            "total_links": len(links_list)
        }
        
        logger.info(f"Successfully fetched topology: {len(devices_list)} devices, {len(links_list)} links")
        
    except requests.exceptions.ConnectionError:
        result["error"] = "Connection error - NetBox server may be unreachable"
        logger.error(f"Connection error to NetBox: {base_url}")
    except requests.exceptions.Timeout:
        result["error"] = "Request timeout - NetBox server did not respond in time"
        logger.error(f"Timeout connecting to NetBox: {base_url}")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            result["error"] = "Authentication failed - invalid API token"
        elif e.response.status_code == 403:
            result["error"] = "Access forbidden - token lacks required permissions"
        else:
            result["error"] = f"HTTP error: {e.response.status_code} - {e.response.reason}"
        logger.error(f"HTTP error from NetBox: {e}")
    except Exception as e:
        result["error"] = f"Error fetching topology: {str(e)}"
        logger.error(f"Error fetching topology from NetBox: {e}")
    
    return result


def get_device_and_interface_report(
    netbox_url: Optional[str] = None,
    netbox_token: Optional[str] = None,
    telnet_host: Optional[str] = None,
    telnet_username: Optional[str] = None,
    telnet_password: Optional[str] = None,
    telnet_command: str = "show interfaces status"
) -> Dict:
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
      can be directly consumed without parsing CLI output. Location: Replace
      get_device_status_from_telnet() call at line 444 with FastDI client request.
    - ELK Integration: Enhance NetBox device list with ELK log analysis to
      identify devices with recent errors or anomalies. This would add a
      "health_score" field based on syslog patterns. Location: Add ELK query
      after NetBox device retrieval (after line 421), before returning result.
    - gNMI Integration: Replace Telnet interface queries with gNMI Subscribe
      for streaming telemetry. This provides real-time interface counters
      and state information. Location: Replace telnet_command execution with
      gNMI subscription to interface state paths.
    
    Args:
        netbox_url: NetBox API URL (defaults to .env NETBOX_URL or demo.netbox.dev)
        netbox_token: NetBox API token (defaults to .env NETBOX_TOKEN)
        telnet_host: Device hostname/IP (defaults to .env TELNET_HOST)
        telnet_username: Telnet username (defaults to .env TELNET_USERNAME)
        telnet_password: Telnet password (defaults to .env TELNET_PASSWORD)
        telnet_command: CLI command to execute (defaults to "show interfaces status")
        
    Returns:
        Dictionary containing:
        - NetBox_Devices: List of device names and roles from NetBox
        - Telnet_Output: First 500 characters of Telnet command output
        - NetBox_Status: Success/failure status of NetBox query
        - Telnet_Status: Success/failure status of Telnet connection
        - error: Error message if operation failed
    """
    logger.info("Generating device and interface report (NetBox + Telnet)")
    
    result = {
        "NetBox_Devices": [],
        "Telnet_Output": "",
        "NetBox_Status": "Not Run",
        "Telnet_Status": "Not Run",
        "error": None
    }
    
    # Load configuration from environment variables if not provided
    if not netbox_url:
        netbox_url = os.getenv("NETBOX_URL", "https://demo.netbox.dev/api/")
    if not netbox_token:
        netbox_token = os.getenv("NETBOX_TOKEN", "")
    if not telnet_host:
        telnet_host = os.getenv("TELNET_HOST", "")
    if not telnet_username:
        telnet_username = os.getenv("TELNET_USERNAME", "")
    if not telnet_password:
        telnet_password = os.getenv("TELNET_PASSWORD", "")
    
    # Step 1: Fetch devices from NetBox
    logger.info(f"Fetching devices from NetBox: {netbox_url}")
    try:
        base_url = netbox_url.rstrip('/')
        if not base_url.endswith('/api'):
            # Ensure we have /api/ in the URL
            if not base_url.endswith('/api/'):
                base_url = f"{base_url.rstrip('/')}/api/"
        else:
            base_url = f"{base_url}/"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Add token if provided
        if netbox_token and netbox_token != "":
            headers["Authorization"] = f"Token {netbox_token}"
        
        devices_url = f"{base_url}dcim/devices/"
        logger.debug(f"NetBox devices URL: {devices_url}")
        
        devices_response = requests.get(devices_url, headers=headers, timeout=10)
        devices_response.raise_for_status()
        devices_data = devices_response.json()
        
        # Extract device names and roles
        devices_list = []
        for device in devices_data.get("results", [])[:10]:  # Limit to first 10 for demo
            device_info = {
                "name": device.get("name"),
                "role": device.get("device_role", {}).get("name") if isinstance(device.get("device_role"), dict) else None,
                "status": device.get("status", {}).get("value") if isinstance(device.get("status"), dict) else None
            }
            devices_list.append(device_info)
        
        result["NetBox_Devices"] = [d["name"] for d in devices_list if d["name"]]
        result["NetBox_Status"] = "Success"
        logger.info(f"Retrieved {len(result['NetBox_Devices'])} devices from NetBox")
        
        # TODO: ELK Integration - Enhance device list with ELK log analysis
        # Example: For each device, query ELK for recent error logs
        # elk_client = ELKClient(endpoint=elk_endpoint)
        # for device in devices_list:
        #     error_count = elk_client.query_error_count(device["name"], hours=24)
        #     device["health_score"] = calculate_health_score(error_count)
        #     device["recent_errors"] = error_count
        # This would add health scoring based on syslog patterns
        
    except requests.exceptions.ConnectionError:
        result["NetBox_Status"] = "Failed"
        result["error"] = "Cannot connect to NetBox API"
        logger.error("NetBox connection error")
    except requests.exceptions.HTTPError as e:
        result["NetBox_Status"] = "Failed"
        if e.response.status_code == 401:
            result["error"] = "NetBox authentication failed"
        else:
            result["error"] = f"NetBox API error: {e.response.status_code}"
        logger.error(f"NetBox HTTP error: {e}")
    except Exception as e:
        result["NetBox_Status"] = "Failed"
        result["error"] = f"NetBox error: {str(e)}"
        logger.error(f"NetBox error: {e}")
    
    # Step 2: Connect via Telnet and run command
    # TODO: FastDI Integration - Replace this Telnet call with FastDI API client
    # Example: fastdi_client.get_device_interfaces(device_id=telnet_host)
    # This would provide structured interface data without CLI parsing
    if telnet_host:
        logger.info(f"Connecting to device via Telnet: {telnet_host}")
        try:
            # Use existing telnet function
            # Future: Replace with FastDI API call for structured telemetry
            telnet_result = get_device_status_from_telnet(
                host=telnet_host,
                username=telnet_username or "",
                password=telnet_password or "",
                command=telnet_command
            )
            
            if telnet_result.get("success"):
                output = telnet_result.get("output", "")
                # Limit to first 500 characters
                result["Telnet_Output"] = output[:500] + ("..." if len(output) > 500 else "")
                result["Telnet_Status"] = "Success"
                logger.info(f"Telnet command executed successfully on {telnet_host}")
            else:
                result["Telnet_Status"] = "Failed"
                result["error"] = telnet_result.get("error", "Telnet connection failed")
                logger.warning(f"Telnet connection failed: {result['error']}")
        except Exception as e:
            result["Telnet_Status"] = "Failed"
            result["error"] = f"Telnet error: {str(e)}"
            logger.error(f"Telnet error: {e}")
    else:
        logger.info("No Telnet host configured, skipping Telnet connection")
        result["Telnet_Status"] = "Skipped"
        result["Telnet_Output"] = "No Telnet host configured in .env or parameters"
    
    logger.info(f"Report generation complete: NetBox={result['NetBox_Status']}, Telnet={result['Telnet_Status']}")
    return result

