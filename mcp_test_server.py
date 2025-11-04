"""MCP Server for Aviz NCP AI Agent.

This agent simulates Aviz NCP's AI infrastructure for validating builds,
monitoring multi-vendor telemetry, and predicting link health.
"""
from mcp.server.fastmcp import FastMCP
from utils.logger import setup_logger
from agents.telemetry_agent import get_port_telemetry as _get_port_telemetry, get_network_topology as _get_network_topology
from agents.ai_agent import predict_link_health as _predict_link_health
from agents.build_agent import validate_build_metadata as _validate_build_metadata

# Initialize logger
logger = setup_logger(__name__)

# Initialize MCP server
mcp = FastMCP("aviz-ncp-ai-agent")
logger.info("Initializing Aviz NCP AI Agent MCP Server")


# -----------------------------
# 1. TELEMETRY TOOLS
# -----------------------------

@mcp.tool()
def get_port_telemetry() -> dict:
    """Simulate SONiC port telemetry metrics."""
    return _get_port_telemetry()


@mcp.tool()
def get_network_topology() -> dict:
    """
    Return a mock network topology with multiple device types.
    
    Simulates a multi-vendor network with SONiC, Cisco, FortiGate, and other devices.
    Returns topology including devices, links, and statistics.
    """
    return _get_network_topology()


# -----------------------------
# 2. AI PREDICTION TOOLS
# -----------------------------

@mcp.tool()
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
    return _predict_link_health(rx_errors, tx_errors, utilization)


# -----------------------------
# 3. BUILD VALIDATION TOOLS
# -----------------------------

@mcp.tool()
def validate_build_metadata(build_json_path: str) -> dict:
    """
    Validate SONiC or non-SONiC build JSON files.
    
    Checks build metadata files for required fields and structure.
    Supports both SONiC and non-SONiC device builds.
    
    Args:
        build_json_path: Path to the build JSON file
        
    Returns:
        Dictionary containing validation results, errors, and warnings
    """
    return _validate_build_metadata(build_json_path)


# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    logger.info("Running Aviz NCP AI Agent prototype...")
    logger.info("Available tools:")
    logger.info("  - get_port_telemetry: Collect SONiC port telemetry")
    logger.info("  - get_network_topology: Get multi-vendor network topology")
    logger.info("  - predict_link_health: AI-based link health prediction")
    logger.info("  - validate_build_metadata: Validate build JSON files")
    logger.info("Waiting for requests on stdio...")
    mcp.run()
