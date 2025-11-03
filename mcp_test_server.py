# mcp_test_server.py
from mcp.server.fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("mock-network-agent")

@mcp.tool()
def get_link_status() -> dict:
    """Return mock SONiC link health data."""
    return {
        "switch": "sonic-leaf-01",
        "interface": "Ethernet12",
        "status": "up",
        "errors": 0,
    }

if __name__ == "__main__":
    print("Running mock-network-agent...")
    print("Waiting for requests on stdio")
    mcp.run()  # Start the server

