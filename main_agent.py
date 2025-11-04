"""Interactive CLI agent for Aviz Networks AI infrastructure.

This agent provides a conversational interface to interact with the MCP server
using natural language queries. It uses an LLM to parse user intent and map
it to appropriate MCP tools, then formats the responses for clear display.
"""
import json
import subprocess
import sys
import os
from typing import Dict, Optional, List, Any

# Try to import tabulate, fallback to simple table formatter
try:
    from tabulate import tabulate
    TABULATE_AVAILABLE = True
except ImportError:
    TABULATE_AVAILABLE = False
    
    def tabulate(data, headers, tablefmt="grid"):
        """Simple table formatter when tabulate is not available."""
        if not data:
            return "No data"
        
        # Calculate column widths
        col_widths = [len(str(h)) for h in headers]
        for row in data:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # Build table
        lines = []
        # Header
        header_line = "| " + " | ".join(str(h).ljust(w) for h, w in zip(headers, col_widths)) + " |"
        lines.append(header_line)
        lines.append("|" + "|".join("-" * (w + 2) for w in col_widths) + "|")
        # Data rows
        for row in data:
            lines.append("| " + " | ".join(str(cell).ljust(w) for cell, w in zip(row, col_widths)) + " |")
        
        return "\n".join(lines)

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try to import OpenAI, fallback to a simple pattern matcher if not available
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class MCPClient:
    """Client for communicating with the MCP server via JSON-RPC."""
    
    def __init__(self, server_process: subprocess.Popen):
        self.proc = server_process
        self.request_id = 1
        
    def send_request(self, method: str, params: Optional[Dict] = None) -> str:
        """Send a JSON-RPC request to the MCP server."""
        req = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        self.request_id += 1
        return json.dumps(req) + "\n"
    
    def read_response(self) -> Optional[Dict]:
        """Read a JSON-RPC response from the MCP server."""
        import time
        max_attempts = 30  # Try up to 30 times (3 seconds total)
        attempt = 0
        
        while attempt < max_attempts:
            try:
                # Check if process is still running
                if self.proc.poll() is not None:
                    # Process has terminated
                    return None
                
                if self.proc.stdout.closed:
                    return None
                
                # Try to read a line
                response_line = self.proc.stdout.readline()
                if response_line:
                    line = response_line.strip()
                    if line:
                        # Try to parse as JSON
                        if line.startswith('{'):
                            try:
                                parsed = json.loads(line)
                                # Verify it's a valid JSON-RPC response
                                if "jsonrpc" in parsed and ("result" in parsed or "error" in parsed):
                                    return parsed
                            except json.JSONDecodeError:
                                # Invalid JSON, continue trying
                                pass
                        # Non-JSON line (likely log output), continue
                
                # Small delay to avoid busy waiting
                time.sleep(0.1)
                attempt += 1
            except Exception as e:
                # Continue trying
                time.sleep(0.1)
                attempt += 1
        
        return None
    
    def call_tool(self, tool_name: str, arguments: Dict) -> Optional[Dict]:
        """Call an MCP tool and return the result."""
        request = self.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        self.proc.stdin.write(request)
        self.proc.stdin.flush()
        
        response = self.read_response()
        if response and "result" in response:
            result = response["result"]
            if "content" in result and len(result["content"]) > 0:
                content_text = result["content"][0].get("text", "{}")
                try:
                    return json.loads(content_text)
                except json.JSONDecodeError:
                    return {"raw_content": content_text}
            return result
        elif response and "error" in response:
            return {"error": response["error"]}
        return None
    
    def initialize(self) -> bool:
        """Initialize the MCP connection."""
        import time
        
        # Give server more time to start (FastMCP needs time to initialize)
        time.sleep(1.0)
        
        init_request = self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "aviz-agent-cli",
                "version": "1.0.0"
            }
        })
        
        try:
            self.proc.stdin.write(init_request)
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            print(f"Error: MCP server process terminated unexpectedly: {e}", file=sys.stderr)
            return False
        
        # Wait for response with longer timeout
        time.sleep(0.3)  # Give server time to process
        init_response = self.read_response()
        
        if init_response and "result" in init_response:
            # Send initialized notification
            initialized_notification = json.dumps({
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }) + "\n"
            try:
                self.proc.stdin.write(initialized_notification)
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                print(f"Error: MCP server process terminated unexpectedly: {e}", file=sys.stderr)
                return False
            return True
        elif init_response and "error" in init_response:
            error = init_response.get("error", {})
            error_msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
            print(f"Error initializing MCP connection: {error_msg}", file=sys.stderr)
            return False
        else:
            # Check if server process is still running
            if self.proc.poll() is not None:
                print(f"Error: MCP server process terminated (exit code: {self.proc.returncode})", file=sys.stderr)
            else:
                print("Error: No valid response from MCP server (server may still be initializing)", file=sys.stderr)
            return False


class QueryParser:
    """Parse natural language queries and map them to MCP tools."""
    
    AVAILABLE_TOOLS = {
        "get_port_telemetry": {
            "description": "Get port telemetry data",
            "parameters": {}
        },
        "get_network_topology": {
            "description": "Get network topology with devices and links",
            "parameters": {}
        },
        "predict_link_health": {
            "description": "Predict link health based on errors and utilization",
            "parameters": ["rx_errors", "tx_errors", "utilization"]
        },
        "validate_build_metadata": {
            "description": "Validate build JSON files",
            "parameters": ["build_json_path"]
        },
        "remediate_link": {
            "description": "Get remediation recommendations for an interface",
            "parameters": ["interface"]
        },
        "get_device_status_from_telnet": {
            "description": "Execute commands on devices via Telnet",
            "parameters": ["host", "username", "password", "command"]
        },
        "get_topology_from_netbox": {
            "description": "Fetch topology from NetBox",
            "parameters": ["base_url", "token"]
        },
        "get_device_and_interface_report": {
            "description": "Get combined NetBox and Telnet device report",
            "parameters": ["netbox_url", "netbox_token", "telnet_host", "telnet_username", "telnet_password", "telnet_command"]
        },
        "get_device_info": {
            "description": "Get device information from YAML inventory",
            "parameters": ["device_name", "query_type"]
        },
        "list_devices_by_vlan": {
            "description": "Find all devices connected to a VLAN ID",
            "parameters": ["vlan_id"]
        },
        "get_vlan_table": {
            "description": "Generate VLAN table showing all VLANs and devices",
            "parameters": []
        },
        "validate_system_health": {
            "description": "Validate system health (AI ONE Center style)",
            "parameters": ["netbox_url", "netbox_token", "elk_endpoint", "servicenow_url", "zendesk_url"]
        }
    }
    
    def __init__(self, use_openai: bool = True, api_key: Optional[str] = None):
        """
        Initialize the query parser.
        
        Args:
            use_openai: Whether to use OpenAI for parsing (defaults to True if available)
            api_key: OpenAI API key (defaults to OPENAI_API_KEY from .env)
        """
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.use_openai = use_openai and OPENAI_AVAILABLE and api_key is not None
        if self.use_openai:
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None
    
    def parse_query(self, query: str) -> Dict[str, Any]:
        """
        Parse a natural language query and return tool name and arguments.
        
        Returns:
            {
                "tool": "tool_name",
                "arguments": {...},
                "confidence": 0.0-1.0
            }
        """
        if self.use_openai:
            return self._parse_with_openai(query)
        else:
            return self._parse_with_patterns(query)
    
    def _parse_with_openai(self, query: str) -> Dict[str, Any]:
        """Use OpenAI to parse the query."""
        tools_schema = {
            "type": "object",
            "properties": {
                "tool": {
                    "type": "string",
                    "enum": list(self.AVAILABLE_TOOLS.keys()),
                    "description": "The MCP tool to call"
                },
                "arguments": {
                    "type": "object",
                    "description": "Arguments for the tool (only include required parameters)"
                }
            },
            "required": ["tool", "arguments"]
        }
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are an AI assistant that maps natural language queries to MCP tools.

Available tools:
{self._format_tools_for_prompt()}

Parse the user's query and return the appropriate tool name and arguments in JSON format.
Only include required parameters. Use empty strings for optional parameters if not specified."""
                    },
                    {"role": "user", "content": query}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            return {
                "tool": result.get("tool"),
                "arguments": result.get("arguments", {}),
                "confidence": 0.9
            }
        except Exception as e:
            print(f"Error parsing query with OpenAI: {e}", file=sys.stderr)
            return self._parse_with_patterns(query)
    
    def _parse_with_patterns(self, query: str) -> Dict[str, Any]:
        """Simple pattern-based query parsing."""
        query_lower = query.lower()
        
        # Pattern matching for common queries
        # VLAN queries
        if "vlan" in query_lower:
            import re
            vlan_match = re.search(r'vlan\s+(\d+)', query_lower)
            if vlan_match:
                vlan_id = int(vlan_match.group(1))
                return {
                    "tool": "list_devices_by_vlan",
                    "arguments": {"vlan_id": vlan_id},
                    "confidence": 0.9
                }
            elif "vlan table" in query_lower or "show vlan" in query_lower:
                return {
                    "tool": "get_vlan_table",
                    "arguments": {},
                    "confidence": 0.9
                }
        
        # Device info queries
        if "which vlan" in query_lower or "vlan is" in query_lower:
            # Try to extract device name
            import re
            device_match = re.search(r'(\S+-\S+|\S+-\d+)', query)
            if device_match:
                device_name = device_match.group(1)
                return {
                    "tool": "get_device_info",
                    "arguments": {"device_name": device_name},
                    "confidence": 0.8
                }
        
        # Device name queries
        device_pattern = r'\b(sonic-\S+|nexus-\S+|edgecore-\S+|celtica-\S+|\S+-\d+)\b'
        import re
        device_match = re.search(device_pattern, query, re.IGNORECASE)
        if device_match and ("info" in query_lower or "vlan" in query_lower or "device" in query_lower):
            device_name = device_match.group(1)
            return {
                "tool": "get_device_info",
                "arguments": {"device_name": device_name},
                "confidence": 0.8
            }
        
        # List devices queries
        if "list all" in query_lower or "show all" in query_lower:
            if "sonic" in query_lower:
                return {
                    "tool": "get_device_info",
                    "arguments": {"query_type": "sonic"},
                    "confidence": 0.8
                }
            elif "device" in query_lower:
                return {
                    "tool": "get_device_info",
                    "arguments": {"query_type": "all"},
                    "confidence": 0.7
                }
        
        # Topology queries
        if "topology" in query_lower or "devices" in query_lower or "network" in query_lower:
            if "netbox" in query_lower:
                return {
                    "tool": "get_topology_from_netbox",
                    "arguments": {"base_url": "", "token": ""},
                    "confidence": 0.7
                }
            else:
                return {
                    "tool": "get_network_topology",
                    "arguments": {},
                    "confidence": 0.8
                }
        
        if "report" in query_lower or ("device" in query_lower and "interface" in query_lower):
            return {
                "tool": "get_device_and_interface_report",
                "arguments": {},
                "confidence": 0.8
            }
        
        if "telemetry" in query_lower or "port" in query_lower:
            return {
                "tool": "get_port_telemetry",
                "arguments": {},
                "confidence": 0.7
            }
        
        if "health" in query_lower and "system" in query_lower:
            return {
                "tool": "validate_system_health",
                "arguments": {},
                "confidence": 0.8
            }
        
        if "health" in query_lower and "link" in query_lower:
            # Try to extract numbers from query
            import re
            numbers = re.findall(r'\d+\.?\d*', query)
            if len(numbers) >= 3:
                return {
                    "tool": "predict_link_health",
                    "arguments": {
                        "rx_errors": int(numbers[0]),
                        "tx_errors": int(numbers[1]),
                        "utilization": float(numbers[2])
                    },
                    "confidence": 0.6
                }
        
        # Default to topology
        return {
            "tool": "get_network_topology",
            "arguments": {},
            "confidence": 0.5
        }
    
    def _format_tools_for_prompt(self) -> str:
        """Format available tools for the OpenAI prompt."""
        lines = []
        for tool_name, tool_info in self.AVAILABLE_TOOLS.items():
            lines.append(f"- {tool_name}: {tool_info['description']}")
            if tool_info['parameters']:
                lines.append(f"  Parameters: {', '.join(tool_info['parameters'])}")
        return "\n".join(lines)


class ResponseRenderer:
    """Render MCP tool responses in formatted output."""
    
    @staticmethod
    def render(response: Dict[str, Any], tool_name: str) -> str:
        """Render a response based on the tool that generated it."""
        if "error" in response:
            return ResponseRenderer._render_error(response)
        
        render_methods = {
            "get_network_topology": ResponseRenderer._render_topology,
            "get_topology_from_netbox": ResponseRenderer._render_netbox_topology,
            "get_device_and_interface_report": ResponseRenderer._render_device_report,
            "get_port_telemetry": ResponseRenderer._render_telemetry,
            "predict_link_health": ResponseRenderer._render_health_prediction,
            "validate_system_health": ResponseRenderer._render_health_validation,
            "get_device_status_from_telnet": ResponseRenderer._render_telnet_output,
            "remediate_link": ResponseRenderer._render_remediation,
            "validate_build_metadata": ResponseRenderer._render_build_validation,
            "get_device_info": ResponseRenderer._render_device_info,
            "list_devices_by_vlan": ResponseRenderer._render_devices_by_vlan,
            "get_vlan_table": ResponseRenderer._render_vlan_table
        }
        
        renderer = render_methods.get(tool_name, ResponseRenderer._render_generic)
        return renderer(response)
    
    @staticmethod
    def _render_error(response: Dict) -> str:
        """Render error response."""
        error_msg = response.get("error", "Unknown error")
        message = response.get("message", "")
        return f"Error: {error_msg}\n{message if message else ''}"
    
    @staticmethod
    def _render_topology(response: Dict) -> str:
        """Render network topology as a table."""
        devices = response.get("devices", [])
        links = response.get("links", [])
        stats = response.get("statistics", {})
        
        output = []
        output.append("\nNetwork Topology Summary")
        output.append("=" * 70)
        output.append(f"Total Devices: {stats.get('total_devices', 0)}")
        output.append(f"SONiC Devices: {stats.get('sonic_devices', 0)}")
        output.append(f"Non-SONiC Devices: {stats.get('non_sonic_devices', 0)}")
        output.append(f"Total Links: {stats.get('total_links', 0)}")
        output.append("")
        
        if devices:
            output.append("Devices:")
            device_table = []
            for device in devices:
                device_table.append([
                    device.get("id", "N/A"),
                    device.get("type", "N/A"),
                    device.get("vendor", "N/A"),
                    device.get("model", "N/A"),
                    device.get("role", "N/A"),
                    device.get("status", "N/A")
                ])
            output.append(tabulate(
                device_table,
                headers=["ID", "Type", "Vendor", "Model", "Role", "Status"],
                tablefmt="grid"
            ))
            output.append("")
        
        if links:
            output.append("Links:")
            link_table = []
            for link in links[:10]:  # Limit to first 10
                link_table.append([
                    link.get("source", "N/A"),
                    link.get("source_port", "N/A"),
                    link.get("target", "N/A"),
                    link.get("target_port", "N/A"),
                    link.get("status", "N/A")
                ])
            output.append(tabulate(
                link_table,
                headers=["Source", "Source Port", "Target", "Target Port", "Status"],
                tablefmt="grid"
            ))
        
        return "\n".join(output)
    
    @staticmethod
    def _render_netbox_topology(response: Dict) -> str:
        """Render NetBox topology."""
        if not response.get("success"):
            return ResponseRenderer._render_error(response)
        
        devices = response.get("devices", [])
        stats = response.get("statistics", {})
        
        output = []
        output.append("\nNetBox Topology")
        output.append("=" * 70)
        output.append(f"Total Devices: {stats.get('total_devices', 0)}")
        output.append(f"Total Links: {stats.get('total_links', 0)}")
        output.append("")
        
        if devices:
            device_table = []
            for device in devices[:20]:  # Limit to first 20
                device_table.append([
                    device.get("name", "N/A"),
                    device.get("device_type", "N/A"),
                    device.get("manufacturer", "N/A"),
                    device.get("role", "N/A"),
                    device.get("status", "N/A"),
                    device.get("primary_ip", "N/A")
                ])
            output.append(tabulate(
                device_table,
                headers=["Name", "Type", "Manufacturer", "Role", "Status", "IP"],
                tablefmt="grid"
            ))
        
        return "\n".join(output)
    
    @staticmethod
    def _render_device_report(response: Dict) -> str:
        """Render device and interface report."""
        output = []
        output.append("\nDevice and Interface Report")
        output.append("=" * 70)
        
        netbox_status = response.get("NetBox_Status", "Unknown")
        telnet_status = response.get("Telnet_Status", "Unknown")
        
        output.append(f"NetBox Status: {netbox_status}")
        output.append(f"Telnet Status: {telnet_status}")
        output.append("")
        
        if netbox_status == "Success":
            devices = response.get("NetBox_Devices", [])
            if devices:
                output.append(f"NetBox Devices ({len(devices)}):")
                for i, device in enumerate(devices[:10], 1):
                    output.append(f"  {i}. {device}")
                if len(devices) > 10:
                    output.append(f"  ... and {len(devices) - 10} more")
                output.append("")
        
        if telnet_status == "Success":
            telnet_output = response.get("Telnet_Output", "")
            if telnet_output:
                output.append("Telnet Command Output:")
                output.append("-" * 70)
                output.append(telnet_output[:500])
                if len(telnet_output) > 500:
                    output.append("... (truncated)")
                output.append("-" * 70)
        
        if response.get("error"):
            output.append(f"\nError: {response['error']}")
        
        return "\n".join(output)
    
    @staticmethod
    def _render_telemetry(response: Dict) -> str:
        """Render port telemetry."""
        output = []
        output.append("\nPort Telemetry")
        output.append("=" * 70)
        output.append(f"Switch: {response.get('switch', 'N/A')}")
        output.append(f"Interface: {response.get('interface', 'N/A')}")
        output.append(f"RX Bytes: {response.get('rx_bytes', 0):,}")
        output.append(f"TX Bytes: {response.get('tx_bytes', 0):,}")
        output.append(f"RX Errors: {response.get('rx_errors', 0)}")
        output.append(f"TX Errors: {response.get('tx_errors', 0)}")
        output.append(f"Utilization: {response.get('utilization', 0):.2%}")
        return "\n".join(output)
    
    @staticmethod
    def _render_health_prediction(response: Dict) -> str:
        """Render link health prediction."""
        output = []
        output.append("\nLink Health Prediction")
        output.append("=" * 70)
        health_score = response.get("health_score", 0)
        status = response.get("status", "unknown")
        output.append(f"Health Score: {health_score:.2%}")
        output.append(f"Status: {status}")
        if "inputs" in response:
            inputs = response["inputs"]
            output.append(f"\nInputs:")
            output.append(f"  RX Errors: {inputs.get('rx_errors', 0)}")
            output.append(f"  TX Errors: {inputs.get('tx_errors', 0)}")
            output.append(f"  Utilization: {inputs.get('utilization', 0):.2%}")
        return "\n".join(output)
    
    @staticmethod
    def _render_health_validation(response: Dict) -> str:
        """Render system health validation."""
        output = []
        output.append("\nSystem Health Validation")
        output.append("=" * 70)
        
        if "Total" in response:
            total = response["Total"]
            output.append(f"Passed: {total.get('Passed', 0)}")
            output.append(f"Failed: {total.get('Failed', 0)}")
            output.append(f"Not Run: {total.get('NotRun', 0)}")
            output.append("")
        
        components = ["NetBox", "Syslog", "ServiceNow", "Zendesk", "FlowAnalytics"]
        component_table = []
        for component in components:
            if component in response:
                status = response[component].get("status", "Unknown")
                details = response[component].get("details", "N/A")
                component_table.append([component, status, details[:50]])
        
        if component_table:
            output.append(tabulate(
                component_table,
                headers=["Component", "Status", "Details"],
                tablefmt="grid"
            ))
        
        return "\n".join(output)
    
    @staticmethod
    def _render_telnet_output(response: Dict) -> str:
        """Render Telnet command output."""
        output = []
        output.append("\nTelnet Command Output")
        output.append("=" * 70)
        if response.get("success"):
            output.append(f"Host: {response.get('host', 'N/A')}")
            output.append(f"Command: {response.get('command', 'N/A')}")
            output.append("\nOutput:")
            output.append("-" * 70)
            output_text = response.get("output", "")
            output.append(output_text[:1000])
            if len(output_text) > 1000:
                output.append("... (truncated)")
        else:
            output.append(f"Error: {response.get('error', 'Unknown error')}")
        return "\n".join(output)
    
    @staticmethod
    def _render_remediation(response: Dict) -> str:
        """Render remediation recommendation."""
        output = []
        output.append("\nRemediation Recommendation")
        output.append("=" * 70)
        output.append(f"Interface: {response.get('interface', 'N/A')}")
        output.append(f"Recommended Action: {response.get('recommended_action', 'N/A')}")
        output.append(f"Reason: {response.get('reason', 'N/A')}")
        output.append(f"Confidence: {response.get('confidence', 0):.2%}")
        return "\n".join(output)
    
    @staticmethod
    def _render_build_validation(response: Dict) -> str:
        """Render build validation result."""
        output = []
        output.append("\nBuild Validation")
        output.append("=" * 70)
        output.append(f"Valid: {response.get('valid', False)}")
        output.append(f"Device Type: {response.get('device_type', 'N/A')}")
        if response.get("errors"):
            output.append(f"\nErrors: {', '.join(response['errors'])}")
        if response.get("warnings"):
            output.append(f"Warnings: {', '.join(response['warnings'])}")
        return "\n".join(output)
    
    @staticmethod
    def _render_device_info(response: Dict) -> str:
        """Render device information response."""
        output = []
        output.append("\nDevice Information")
        output.append("=" * 70)
        
        if not response.get("success", True):
            output.append(f"Error: {response.get('error', 'Unknown error')}")
            return "\n".join(output)
        
        if "device" in response:
            # Single device
            device = response["device"]
            output.append(f"Device: {device.get('name', 'N/A')}")
            output.append(f"IP: {device.get('ip', 'N/A')}")
            output.append(f"Vendor: {device.get('vendor', 'N/A')}")
            output.append(f"OS: {device.get('os', 'N/A')}")
            output.append(f"Role: {device.get('role', 'N/A')}")
            
            vlans = device.get("vlans", [])
            if vlans:
                output.append("\nVLANs:")
                for vlan in vlans:
                    if isinstance(vlan, dict):
                        output.append(f"  - VLAN {vlan.get('id', 'N/A')}: {vlan.get('name', 'N/A')}")
                    else:
                        output.append(f"  - VLAN {vlan}")
        else:
            # Multiple devices
            devices = response.get("devices", [])
            count = response.get("count", len(devices))
            output.append(f"Found {count} device(s)")
            output.append("")
            
            if devices:
                device_table = []
                for device in devices:
                    vlans_str = ", ".join([f"{v.get('id', v) if isinstance(v, dict) else v}" for v in device.get("vlans", [])])
                    device_table.append([
                        device.get("name", "N/A"),
                        device.get("ip", "N/A"),
                        device.get("vendor", "N/A"),
                        device.get("os", "N/A"),
                        device.get("role", "N/A"),
                        vlans_str[:30] + ("..." if len(vlans_str) > 30 else "")
                    ])
                output.append(tabulate(
                    device_table,
                    headers=["Name", "IP", "Vendor", "OS", "Role", "VLANs"],
                    tablefmt="grid"
                ))
        
        # Show grouped results if available
        if "grouped_by_role" in response:
            output.append("\nGrouped by Role:")
            for role, role_devices in response["grouped_by_role"].items():
                output.append(f"  {role}: {len(role_devices)} device(s)")
        
        return "\n".join(output)
    
    @staticmethod
    def _render_devices_by_vlan(response: Dict) -> str:
        """Render devices by VLAN response."""
        output = []
        output.append("\nDevices by VLAN")
        output.append("=" * 70)
        
        vlan_id = response.get("vlan_id", "N/A")
        devices = response.get("devices", [])
        count = response.get("count", 0)
        
        output.append(f"VLAN ID: {vlan_id}")
        output.append(f"Found {count} device(s)")
        output.append("")
        
        if devices:
            device_table = []
            for device in devices:
                vlan_info = device.get("vlan", {})
                vlan_name = vlan_info.get("name", "N/A") if isinstance(vlan_info, dict) else "N/A"
                device_table.append([
                    device.get("name", "N/A"),
                    device.get("ip", "N/A"),
                    device.get("vendor", "N/A"),
                    device.get("os", "N/A"),
                    device.get("role", "N/A"),
                    vlan_name
                ])
            output.append(tabulate(
                device_table,
                headers=["Device", "IP", "Vendor", "OS", "Role", "VLAN Name"],
                tablefmt="grid"
            ))
        else:
            output.append("No devices found for this VLAN")
        
        return "\n".join(output)
    
    @staticmethod
    def _render_vlan_table(response: Dict) -> str:
        """Render VLAN table response."""
        output = []
        output.append("\nVLAN Table")
        output.append("=" * 70)
        
        vlan_table = response.get("vlan_table", [])
        total_vlans = response.get("total_vlans", 0)
        total_devices = response.get("total_devices", 0)
        
        output.append(f"Total VLANs: {total_vlans}")
        output.append(f"Total Devices: {total_devices}")
        output.append("")
        
        if vlan_table:
            # Create table with VLAN ID, Name, and Device Count
            table_data = []
            for vlan_entry in vlan_table:
                device_count = len(vlan_entry.get("devices", []))
                device_names = ", ".join([d.get("name", "N/A") for d in vlan_entry.get("devices", [])[:5]])
                if device_count > 5:
                    device_names += f" ... and {device_count - 5} more"
                table_data.append([
                    vlan_entry.get("vlan_id", "N/A"),
                    vlan_entry.get("vlan_name", "N/A"),
                    device_count,
                    device_names[:50] + ("..." if len(device_names) > 50 else "")
                ])
            
            output.append(tabulate(
                table_data,
                headers=["VLAN ID", "VLAN Name", "Device Count", "Devices"],
                tablefmt="grid"
            ))
        else:
            output.append("No VLAN data available")
        
        return "\n".join(output)
    
    @staticmethod
    def _render_generic(response: Dict) -> str:
        """Render generic JSON response."""
        return json.dumps(response, indent=2)


def main():
    """
    Main entry point for the interactive agent.
    
    The agent launches the MCP server as a subprocess and communicates with it
    via stdio (JSON-RPC). This is required because FastMCP uses stdio for transport.
    
    Usage:
        python main_agent.py
    
    Environment Variables:
        OPENAI_API_KEY: OpenAI API key for LLM-based query parsing (optional)
        NETBOX_URL: NetBox API URL (optional, loaded from .env)
        NETBOX_TOKEN: NetBox API token (optional, loaded from .env)
        TELNET_HOST: Telnet device hostname (optional, loaded from .env)
        TELNET_USERNAME: Telnet username (optional, loaded from .env)
        TELNET_PASSWORD: Telnet password (optional, loaded from .env)
    """
    print("Aviz AI Agent ready. Ask me about your network.")
    print()
    
    # Launch MCP server as subprocess
    # Note: FastMCP uses stdio for communication, so we must launch it as a subprocess
    # The server will run in the background and communicate via stdin/stdout pipes
    try:
        proc = subprocess.Popen(
            [sys.executable, "mcp_server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0
        )
    except Exception as e:
        print(f"Error: Failed to launch MCP server: {e}")
        print("Make sure mcp_server.py is in the current directory")
        sys.exit(1)
    
    # Wait a moment and check if server started successfully
    import time
    import threading
    
    # Read stderr in background to capture any errors
    stderr_lines = []
    def read_stderr():
        for line in proc.stderr:
            stderr_lines.append(line)
    
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stderr_thread.start()
    
    time.sleep(2.0)  # Give server more time to fully initialize
    
    # Check if server process is still running
    if proc.poll() is not None:
        # Server crashed, show error output
        print(f"Error: MCP server crashed during startup (exit code: {proc.returncode})")
        if stderr_lines:
            print("\nServer error output:")
            print("".join(stderr_lines[-20:]))  # Last 20 lines
        sys.exit(1)
    
    # Initialize MCP client
    mcp_client = MCPClient(proc)
    if not mcp_client.initialize():
        print("Error: Failed to initialize MCP connection")
        # Try to get server error output
        try:
            stderr_output = proc.stderr.read()
            if stderr_output:
                print("\nServer error output:")
                print(stderr_output[-500:])
        except:
            pass
        proc.terminate()
        proc.wait()
        sys.exit(1)
    
    # Initialize query parser
    # Check for OpenAI API key in environment
    openai_api_key = os.getenv("OPENAI_API_KEY")
    use_openai = OPENAI_AVAILABLE and openai_api_key is not None
    
    if use_openai:
        print("Using OpenAI for query parsing")
    else:
        if not OPENAI_AVAILABLE:
            print("Note: OpenAI package not installed. Using pattern-based query parsing.")
            print("      Install with: pip install openai")
        elif not openai_api_key:
            print("Note: OPENAI_API_KEY not set. Using pattern-based query parsing.")
            print("      Set OPENAI_API_KEY in .env for LLM support.")
    print()
    
    parser = QueryParser(use_openai=use_openai)
    renderer = ResponseRenderer()
    
    # Interactive loop
    while True:
        try:
            query = input("\n> ").strip()
            
            if not query:
                continue
            
            if query.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
            
            if query.lower() == "help":
                print("\nAvailable commands:")
                print("  - Ask questions about network topology, devices, interfaces")
                print("  - Examples:")
                print("    'Show me the network topology'")
                print("    'List all devices from NetBox'")
                print("    'Get device and interface report'")
                print("    'What is the port telemetry?'")
                print("    'Validate system health'")
                print("    'Which VLAN is this device on?'")
                print("    'List all interfaces for sonic-leaf-01'")
                print("    'Summarize traffic utilization'")
                print("  - Type 'quit' or 'exit' to exit")
                print("\nAvailable MCP Tools:")
                for tool_name, tool_info in parser.AVAILABLE_TOOLS.items():
                    print(f"  - {tool_name}: {tool_info['description']}")
                continue
            
            # Parse query
            parsed = parser.parse_query(query)
            tool_name = parsed.get("tool")
            arguments = parsed.get("arguments", {})
            confidence = parsed.get("confidence", 0.0)
            
            if not tool_name:
                print("Error: Could not determine which tool to call")
                print("Try rephrasing your question or type 'help' for examples")
                continue
            
            # Filter out empty string arguments (they're optional and shouldn't be sent)
            arguments = {k: v for k, v in arguments.items() if v != ""}
            
            # Call MCP tool
            response = mcp_client.call_tool(tool_name, arguments)
            
            if response:
                # Render response
                output = renderer.render(response, tool_name)
                print(output)
            else:
                print("Error: No response from MCP server")
        
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except BrokenPipeError:
            print("\nError: Connection to MCP server lost")
            print("The server may have terminated unexpectedly")
            break
        except Exception as e:
            print(f"Error: {e}")
            # Only print full traceback in debug mode
            if os.getenv("DEBUG", "").lower() in ("1", "true", "yes"):
                import traceback
                traceback.print_exc()
    
    # Cleanup
    try:
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
        proc.wait()


if __name__ == "__main__":
    main()

