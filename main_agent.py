"""Interactive CLI agent for Aviz Networks AI infrastructure.

This agent provides a conversational interface to interact with the MCP server
using natural language queries. It uses an LLM to parse user intent and map
it to appropriate MCP tools, then formats the responses for clear display.
"""
import json
import subprocess
import sys
import os
import time
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


class CoordinatorResponseRenderer:
    """Renderer for coordinator agent responses."""
    
    @staticmethod
    def _format_table(data: List[List[Any]], headers: List[str]) -> str:
        """Format table data with fallback if tabulate is not available."""
        if TABULATE_AVAILABLE:
            return tabulate(data, headers=headers, tablefmt="grid")
        else:
            # Simple fallback table formatter
            output = []
            # Calculate column widths
            col_widths = [len(str(h)) for h in headers]
            for row in data:
                for i, cell in enumerate(row):
                    if i < len(col_widths):
                        col_widths[i] = max(col_widths[i], len(str(cell)))
            
            # Print header
            header_line = " | ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers))
            output.append(header_line)
            output.append("-" * len(header_line))
            
            # Print rows
            for row in data:
                row_line = " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
                output.append(row_line)
            
            return "\n".join(output)
    
    @staticmethod
    def render(result: Dict[str, Any]) -> str:
        """Render coordinator response with combined results from multiple agents."""
        output = []
        
        # Summary
        summary = result.get("summary", "Query executed")
        output.append("\n" + "=" * 70)
        output.append("Query Result")
        output.append("=" * 70)
        output.append(f"Summary: {summary}")
        output.append("")
        
        # Agents called``
        agents_called = result.get("agents_called", [])
        if agents_called:
            output.append(f"Agents invoked: {', '.join(agents_called)}")
            output.append("")
        
        # Errors
        errors = result.get("errors", {})
        if errors:
            output.append("Errors:")
            for agent, error in errors.items():
                output.append(f"  {agent}: {error}")
            output.append("")
        
        # Results from each agent
        results = result.get("results", {})
        for agent_name, agent_result in results.items():
            if agent_name in errors:
                continue
            
            output.append(f"\n{agent_name.title()} Agent Results:")
            output.append("-" * 70)
            
            if isinstance(agent_result, dict):
                query_type = agent_result.get("query_type", "unknown")
                data = agent_result.get("data", {})
                agent_summary = agent_result.get("summary", "")
                
                output.append(f"Query Type: {query_type}")
                if agent_summary:
                    output.append(f"Summary: {agent_summary}")
                output.append("")
                
                # Render data based on type
                if query_type == "device_info":
                    # Check if it's a single device or multiple devices
                    if "device" in data:
                        # Single device - show as table for consistency
                        device = data["device"]
                        device_table = [[
                            device.get('name', 'N/A'),
                            device.get('ip', 'N/A'),
                            device.get('vendor', 'N/A'),
                            device.get('os', 'N/A'),
                            device.get('role', 'N/A'),
                            ", ".join([f"VLAN {v.get('id', v) if isinstance(v, dict) else v}" for v in device.get('vlans', [])])
                        ]]
                        output.append(CoordinatorResponseRenderer._format_table(
                            device_table,
                            ["Device", "IP", "Vendor", "OS", "Role", "VLANs"]
                        ))
                    elif "devices" in data:
                        # Multiple devices - show as table
                        devices = data["devices"]
                        device_table = []
                        for device in devices:
                            vlans_str = ", ".join([f"VLAN {v.get('id', v) if isinstance(v, dict) else v}" for v in device.get("vlans", [])])
                            device_table.append([
                                device.get("name", "N/A"),
                                device.get("ip", "N/A"),
                                device.get("vendor", "N/A"),
                                device.get("os", "N/A"),
                                device.get("role", "N/A"),
                                vlans_str[:50] + ("..." if len(vlans_str) > 50 else "")
                            ])
                        output.append(CoordinatorResponseRenderer._format_table(
                            device_table,
                            ["Device", "IP", "Vendor", "OS", "Role", "VLANs"]
                        ))
                    elif isinstance(data, dict) and "success" in data:
                        # Fallback to nested device info
                        if "device" in data:
                            device = data["device"]
                            device_table = [[
                                device.get('name', 'N/A'),
                                device.get('ip', 'N/A'),
                                device.get('vendor', 'N/A'),
                                device.get('os', 'N/A'),
                                device.get('role', 'N/A'),
                                ", ".join([f"VLAN {v.get('id', v) if isinstance(v, dict) else v}" for v in device.get('vlans', [])])
                            ]]
                            output.append(CoordinatorResponseRenderer._format_table(
                                device_table,
                                ["Device", "IP", "Vendor", "OS", "Role", "VLANs"]
                            ))
                
                elif query_type == "vlan_lookup":
                    devices = data.get("devices", [])
                    if devices:
                        device_table = []
                        for device in devices:
                            device_table.append([
                                device.get("name", "N/A"),
                                device.get("ip", "N/A"),
                                device.get("vendor", "N/A"),
                                device.get("role", "N/A")
                            ])
                        output.append(CoordinatorResponseRenderer._format_table(
                            device_table,
                            ["Device", "IP", "Vendor", "Role"]
                        ))
                
                elif query_type == "error_threshold" or query_type == "high_utilization":
                    devices = data if isinstance(data, list) else []
                    if devices:
                        device_table = []
                        for device in devices:
                            device_table.append([
                                device.get("device", "N/A"),
                                device.get("interface", "N/A"),
                                device.get("rx_errors", 0),
                                device.get("tx_errors", 0),
                                f"{device.get('utilization', 0):.1%}"
                            ])
                        output.append(CoordinatorResponseRenderer._format_table(
                            device_table,
                            ["Device", "Interface", "RX Errors", "TX Errors", "Utilization"]
                        ))
                
                elif query_type == "firmware_check":
                    devices = data if isinstance(data, list) else []
                    if devices:
                        device_table = []
                        for device in devices:
                            device_table.append([
                                device.get("device", "N/A"),
                                device.get("current_version", "N/A"),
                                device.get("target_version", "N/A")
                            ])
                        output.append(CoordinatorResponseRenderer._format_table(
                            device_table,
                            ["Device", "Current Version", "Target Version"]
                        ))
                
                elif query_type == "open_tickets" or query_type == "high_priority" or query_type == "device_tickets" or query_type == "servicenow_tickets" or query_type == "zendesk_tickets" or query_type == "all_tickets":
                    tickets = data if isinstance(data, list) else []
                    if tickets:
                        ticket_table = []
                        for ticket in tickets:
                            ticket_table.append([
                                ticket.get("id", "N/A"),
                                ticket.get("title", "N/A")[:40],
                                ticket.get("device", "N/A"),
                                ticket.get("priority", "N/A"),
                                ticket.get("status", "N/A"),
                                ticket.get("source", "N/A")
                            ])
                        output.append(CoordinatorResponseRenderer._format_table(
                            ticket_table,
                            ["Ticket ID", "Title", "Device", "Priority", "Status", "Source"]
                        ))
                    else:
                        output.append("No tickets found")
                
                elif query_type == "interface_status" or query_type == "sample_telemetry" or query_type == "all_telemetry":
                    # Handle telemetry data
                    telemetry_list = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
                    if telemetry_list:
                        telemetry_table = []
                        for entry in telemetry_list:
                            telemetry_table.append([
                                entry.get("device", "N/A"),
                                entry.get("interface", "N/A"),
                                f"{entry.get('rx_bytes', 0):,}",
                                f"{entry.get('tx_bytes', 0):,}",
                                entry.get("rx_errors", 0),
                                entry.get("tx_errors", 0),
                                f"{entry.get('utilization', 0):.1%}"
                            ])
                        output.append(CoordinatorResponseRenderer._format_table(
                            telemetry_table,
                            ["Device", "Interface", "RX Bytes", "TX Bytes", "RX Errors", "TX Errors", "Utilization"]
                        ))
                    else:
                        output.append("No telemetry data available")
                
                elif query_type == "vlan_table":
                    # Handle VLAN table
                    vlan_table_data = data.get("vlan_table", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    if vlan_table_data:
                        vlan_table = []
                        for vlan_entry in vlan_table_data:
                            device_count = len(vlan_entry.get("devices", []))
                            device_names = ", ".join([d.get("name", "N/A") for d in vlan_entry.get("devices", [])[:5]])
                            if device_count > 5:
                                device_names += f" ... and {device_count - 5} more"
                            vlan_table.append([
                                vlan_entry.get("vlan_id", "N/A"),
                                vlan_entry.get("vlan_name", "N/A"),
                                device_count,
                                device_names[:60] + ("..." if len(device_names) > 60 else "")
                            ])
                        output.append(CoordinatorResponseRenderer._format_table(
                            vlan_table,
                            ["VLAN ID", "VLAN Name", "Device Count", "Devices"]
                        ))
                    else:
                        output.append("No VLAN data available")
                
                elif isinstance(data, (dict, list)) and query_type not in ["unknown", "baseline", "config_status"]:
                    # For unknown query types, try to detect if it's tabular data
                    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                        # Try to create a table from list of dicts
                        keys = list(data[0].keys())
                        if keys:
                            table_data = []
                            for item in data:
                                row = [str(item.get(k, "N/A"))[:50] for k in keys]
                                table_data.append(row)
                            output.append(CoordinatorResponseRenderer._format_table(
                                table_data,
                                keys
                            ))
                        else:
                            output.append(json.dumps(data, indent=2))
                    else:
                        output.append(json.dumps(data, indent=2))
                else:
                    # Fallback for other types
                    if isinstance(data, dict) and len(data) > 0:
                        output.append(json.dumps(data, indent=2))
        
        # Structured data overview
        structured_data = result.get("structured_data", {})
        if structured_data:
            output.append("\n" + "-" * 70)
            output.append("Combined Data Overview:")
            output.append(f"  Devices: {len(structured_data.get('devices', []))}")
            output.append(f"  Telemetry entries: {len(structured_data.get('telemetry', []))}")
            output.append(f"  Config issues: {len(structured_data.get('config_issues', []))}")
            output.append(f"  Tickets: {len(structured_data.get('tickets', []))}")
        
        return "\n".join(output)


def _parse_inventory_command(args: List[str]) -> Optional[Dict[str, Any]]:
    """
    Parse inventory CLI commands.
    
    Commands:
        inventory list --by vendor --value Cisco --format table
        inventory summary --format markdown
        inventory mismatches --identity-check --format table
        inventory report --export html
    """
    if not args or args[0] != "inventory":
        return None
    
    if len(args) < 2:
        return {"error": "Inventory command required: list, summary, mismatches, or report"}
    
    subcommand = args[1].lower()
    
    # Parse arguments
    filter_by = None
    filter_value = None
    format_type = "table"
    export_format = "none"
    identity_check = False
    
    i = 2
    while i < len(args):
        if args[i] == "--by" and i + 1 < len(args):
            filter_by = args[i + 1]
            i += 2
        elif args[i] == "--value" and i + 1 < len(args):
            filter_value = args[i + 1]
            i += 2
        elif args[i] == "--format" and i + 1 < len(args):
            format_type = args[i + 1]
            i += 2
        elif args[i] == "--export" and i + 1 < len(args):
            export_format = args[i + 1]
            i += 2
        elif args[i] == "--identity-check":
            identity_check = True
            i += 1
        else:
            i += 1
    
    # Import inventory functions
    from agents.inventory_agent import (
        load_yaml_inventory, load_netbox_inventory, merge_inventories,
        group_by, detect_mismatches, optional_identity_verify
    )
    from agents.inventory_models import InventoryReport
    from utils.renderers import to_table, to_json, to_markdown_report, to_html_report
    from pathlib import Path
    
    try:
        yaml_snap = load_yaml_inventory()
        netbox_snap = load_netbox_inventory()
        merged = merge_inventories(yaml_snap, netbox_snap)
        
        if subcommand == "list":
            devices = merged.devices
            if filter_by and filter_value:
                if filter_by == "vlan_id":
                    vlan_id = int(filter_value)
                    devices = [d for d in devices if any(v.id == vlan_id for v in d.vlans)]
                else:
                    devices = [d for d in devices if str(getattr(d, filter_by, "")).lower() == filter_value.lower()]
            
            if format_type == "json":
                print(to_json([d.to_dict() for d in devices]))
            elif format_type == "markdown":
                report = InventoryReport(passed=len(devices), groups={})
                print(to_markdown_report(merged, report, include_mismatches=False))
            else:
                print(to_table(devices))
            return {"success": True}
        
        elif subcommand == "summary":
            vendor_groups = group_by(merged, "vendor")
            role_groups = group_by(merged, "role")
            os_groups = group_by(merged, "os")
            region_groups = group_by(merged, "region")
            
            totals = {
                "total_devices": len(merged.devices),
                "by_vendor": {k: len(v) for k, v in vendor_groups.items()},
                "by_role": {k: len(v) for k, v in role_groups.items()},
                "by_os": {k: len(v) for k, v in os_groups.items()},
                "by_region": {k: len(v) for k, v in region_groups.items()}
            }
            
            if format_type == "json":
                print(to_json(totals))
            elif format_type == "markdown":
                lines = ["# Inventory Summary", "", f"**Total Devices:** {totals['total_devices']}", "", "## By Vendor", ""]
                for vendor, count in totals["by_vendor"].items():
                    lines.append(f"- {vendor}: {count}")
                lines.extend(["", "## By Role", ""])
                for role, count in totals["by_role"].items():
                    lines.append(f"- {role}: {count}")
                lines.extend(["", "## By OS", ""])
                for os_type, count in totals["by_os"].items():
                    lines.append(f"- {os_type}: {count}")
                print("\n".join(lines))
            else:
                try:
                    from tabulate import tabulate
                    table_data = [["Category", "Value", "Count"]]
                    table_data.append(["Total Devices", "", totals["total_devices"]])
                    for vendor, count in totals["by_vendor"].items():
                        table_data.append(["Vendor", vendor, count])
                    for role, count in totals["by_role"].items():
                        table_data.append(["Role", role, count])
                    for os_type, count in totals["by_os"].items():
                        table_data.append(["OS", os_type, count])
                    print(tabulate(table_data, headers="firstrow", tablefmt="grid"))
                except ImportError:
                    print(f"Total Devices: {totals['total_devices']}")
                    print("\nBy Vendor:")
                    for vendor, count in totals["by_vendor"].items():
                        print(f"  {vendor}: {count}")
            return {"success": True}
        
        elif subcommand == "mismatches":
            mismatches = detect_mismatches(yaml_snap, netbox_snap)
            if identity_check:
                identity_mismatches = optional_identity_verify(merged.devices, enabled=True)
                mismatches.extend(identity_mismatches)
            
            if format_type == "json":
                print(to_json([m.to_dict() for m in mismatches]))
            elif format_type == "markdown":
                lines = ["# Inventory Mismatches", "", f"**Total Mismatches:** {len(mismatches)}", "",
                        "| Device | Category | Expected | Observed | Details |",
                        "|--------|----------|----------|----------|---------|"]
                for m in mismatches:
                    details = m.details or ""
                    lines.append(f"| {m.device_name} | {m.category} | {m.expected} | {m.observed} | {details} |")
                print("\n".join(lines))
            else:
                try:
                    from tabulate import tabulate
                    table_data = [[m.device_name, m.category, str(m.expected), str(m.observed), (m.details or "")[:50]] 
                                for m in mismatches]
                    print(tabulate(table_data, headers=["Device", "Category", "Expected", "Observed", "Details"], tablefmt="grid"))
                except ImportError:
                    for m in mismatches:
                        print(f"{m.device_name}: {m.category} - Expected {m.expected}, Got {m.observed}")
            return {"success": True}
        
        elif subcommand == "report":
            mismatches = detect_mismatches(yaml_snap, netbox_snap)
            vendor_groups = group_by(merged, "vendor")
            role_groups = group_by(merged, "role")
            os_groups = group_by(merged, "os")
            region_groups = group_by(merged, "region")
            
            report = InventoryReport(
                passed=len(merged.devices) - len(mismatches),
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
            
            if export_format != "none":
                artifacts_dir = Path("artifacts")
                artifacts_dir.mkdir(exist_ok=True)
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                if export_format == "md":
                    markdown = to_markdown_report(merged, report)
                    file_path = artifacts_dir / f"inventory_report_{timestamp}.md"
                    with open(file_path, 'w') as f:
                        f.write(markdown)
                    print(f"Report exported to: {file_path}")
                elif export_format == "html":
                    markdown = to_markdown_report(merged, report)
                    html = to_html_report(markdown, title="Inventory Report")
                    file_path = artifacts_dir / f"inventory_report_{timestamp}.html"
                    with open(file_path, 'w') as f:
                        f.write(html)
                    print(f"Report exported to: {file_path}")
                elif export_format == "json":
                    report_data = {"snapshot": merged.to_dict(), "report": report.to_dict()}
                    file_path = artifacts_dir / f"inventory_report_{timestamp}.json"
                    with open(file_path, 'w') as f:
                        f.write(to_json(report_data))
                    print(f"Report exported to: {file_path}")
            else:
                # Print summary
                print(f"Inventory Report Summary:")
                print(f"  Total Devices: {len(merged.devices)}")
                print(f"  Mismatches: {len(mismatches)}")
                print(f"  Passed: {report.passed}")
                print(f"  Failed: {report.failed}")
            return {"success": True}
        
        else:
            return {"error": f"Unknown inventory command: {subcommand}"}
    except Exception as e:
        return {"error": str(e)}


def main():
    """
    Main entry point for the interactive multi-agent coordinator system.
    
    This agent uses a coordinator to route queries to domain-specific sub-agents
    (Inventory, Telemetry, Config, Ticketing) and combines their responses.
    
    Usage:
        python main_agent.py
        
    CLI Commands:
        inventory list --by vendor --value Cisco --format table
        inventory summary --format markdown
        inventory mismatches --identity-check --format table
        inventory report --export html
    
    Environment Variables:
        OPENAI_API_KEY: OpenAI API key for LLM-based query parsing (optional)
    """
    import sys
    
    # Check for CLI arguments
    if len(sys.argv) > 1:
        # Parse CLI command
        result = _parse_inventory_command(sys.argv[1:])
        if result:
            if "error" in result:
                print(f"Error: {result['error']}", file=sys.stderr)
                sys.exit(1)
            sys.exit(0)
    
    print("Aviz AI Agent (Multi-Agent Coordinator) ready. Ask me about your network.")
    print()
    
    # Initialize coordinator agent
    from agents.coordinator_agent import get_coordinator
    coordinator = get_coordinator()
    
    # Initialize response renderer for coordinator output
    renderer = CoordinatorResponseRenderer()
    
    # Conversational memory
    conversation_context = []
    
    # Interactive loop
    while True:
        try:
            query = input("\n> ").strip()
            
            if not query:
                continue
            
            if query.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
            
            # Check for CLI-style inventory commands
            if query.startswith("inventory "):
                result = _parse_inventory_command(query.split())
                if result and "error" in result:
                    print(f"Error: {result['error']}")
                continue
            
            if query.lower() == "help":
                print("\nAvailable commands:")
                print("  - Ask questions about network devices, telemetry, configuration, tickets")
                print("  - Examples:")
                print("    'Which VLAN is sonic-leaf-01 on?'")
                print("    'List all devices on VLAN 103'")
                print("    'Show devices with rx_errors > 5'")
                print("    'List all SONiC devices'")
                print("    'Show high priority tickets'")
                print("    'List devices with outdated firmware'")
                print("    'Compare config drift and utilization for all SONiC switches'")
                print("    'Show me all devices with high CPU usage and open ServiceNow tickets'")
                print("  - Type 'quit' or 'exit' to exit")
                print("  - Type 'clear' to clear conversation context")
                print("\nInventory CLI Commands:")
                print("  inventory list --by vendor --value Cisco --format table")
                print("  inventory summary --format markdown")
                print("  inventory mismatches --identity-check --format table")
                print("  inventory report --export html")
                print("\nAvailable Agents:")
                print("  - Inventory: Device inventory, VLANs, device information")
                print("  - Telemetry: Interface status, errors, utilization, CPU/memory")
                print("  - Config: Firmware versions, configuration compliance, drift")
                print("  - Ticketing: ServiceNow, Zendesk tickets, incidents")
                continue
           
            if query.lower() == "clear":
                conversation_context = []
                print("Conversation context cleared")
                continue
            
            # Build context from conversation history
            context = {
                "history": conversation_context[-5:],  # Last 5 queries
                "session_id": "default"
            }
            
            # Execute query through coordinator
            result = coordinator.execute_query(query, context)
            
            # Update conversation context
            conversation_context.append({
                "query": query,
                "agents": result.get("agents_called", []),
                "timestamp": time.time()
            })
            
            # Render coordinator response
            output = renderer.render(result)
            print(output)
        
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            # Only print full traceback in debug mode
            if os.getenv("DEBUG", "").lower() in ("1", "true", "yes"):
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    main()

