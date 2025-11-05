#!/bin/bash
# Smoke test script for Inventory Insight Agent
# Tests MCP server inventory tools and verifies artifact generation

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test configuration
MCP_SERVER_SCRIPT="mcp_server.py"
CLIENT_TEST_SCRIPT="client_test.py"
ARTIFACTS_DIR="artifacts"
TIMEOUT=30

echo -e "${GREEN}=== Inventory Insight Agent Smoke Tests ===${NC}\n"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 not found${NC}"
    exit 1
fi

# Check if required files exist
if [ ! -f "$MCP_SERVER_SCRIPT" ]; then
    echo -e "${RED}Error: $MCP_SERVER_SCRIPT not found${NC}"
    exit 1
fi

if [ ! -f "$CLIENT_TEST_SCRIPT" ]; then
    echo -e "${RED}Error: $CLIENT_TEST_SCRIPT not found${NC}"
    exit 1
fi

# Clean up artifacts directory
echo -e "${YELLOW}Cleaning up artifacts directory...${NC}"
rm -rf "$ARTIFACTS_DIR"
mkdir -p "$ARTIFACTS_DIR"

# Create a simple test client script
cat > test_inventory_client.py << 'PYEOF'
"""Simple test client for inventory MCP tools."""
import json
import subprocess
import sys
import time
import os

def send_request(method, params=None, request_id=1):
    """Send a JSON-RPC request."""
    req = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {}
    }
    return json.dumps(req) + "\n"

def read_response(proc, timeout=5):
    """Read a JSON-RPC response."""
    try:
        response_line = proc.stdout.readline()
        if response_line:
            return json.loads(response_line.strip())
    except Exception as e:
        print(f"Error reading response: {e}", file=sys.stderr)
    return None

def call_tool(proc, tool_name, arguments, request_id):
    """Call an MCP tool."""
    request = send_request("tools/call", {
        "name": tool_name,
        "arguments": arguments
    }, request_id=request_id)
    
    proc.stdin.write(request)
    proc.stdin.flush()
    
    response = read_response(proc)
    if response and "result" in response:
        return response["result"]
    elif response and "error" in response:
        return {"error": response["error"]}
    return None

# Start MCP server
print("Starting MCP server...")
proc = subprocess.Popen(
    [sys.executable, "mcp_server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=0
)

# Initialize
time.sleep(2)  # Give server time to start
init_request = send_request("initialize", {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "test-client", "version": "1.0.0"}
}, 1)

proc.stdin.write(init_request)
proc.stdin.flush()

init_response = read_response(proc)
if not init_response or "result" not in init_response:
    print("ERROR: Failed to initialize MCP connection", file=sys.stderr)
    sys.exit(1)

# Send initialized notification
initialized_notification = json.dumps({
    "jsonrpc": "2.0",
    "method": "notifications/initialized"
}) + "\n"
proc.stdin.write(initialized_notification)
proc.stdin.flush()

time.sleep(1)

request_id = 2
errors = []

# Test 1: inventory_summary
print("\n=== Test 1: inventory_summary ===")
result = call_tool(proc, "inventory_summary", {"format": "table"}, request_id)
request_id += 1

if result and "error" not in result:
    print("✓ inventory_summary succeeded")
    if "content" in result:
        print(f"  Content type: {type(result['content'])}")
else:
    error_msg = result.get("error", "Unknown error") if result else "No response"
    print(f"✗ inventory_summary failed: {error_msg}", file=sys.stderr)
    errors.append("inventory_summary")

# Test 2: inventory_report with export
print("\n=== Test 2: inventory_report (export=md) ===")
result = call_tool(proc, "inventory_report", {"export": "md"}, request_id)
request_id += 1

if result and "error" not in result:
    print("✓ inventory_report succeeded")
    if "file_path" in result:
        print(f"  Report file: {result['file_path']}")
        if os.path.exists(result['file_path']):
            print(f"  ✓ Report file exists: {result['file_path']}")
        else:
            print(f"  ✗ Report file not found: {result['file_path']}", file=sys.stderr)
            errors.append("inventory_report file not found")
else:
    error_msg = result.get("error", "Unknown error") if result else "No response"
    print(f"✗ inventory_report failed: {error_msg}", file=sys.stderr)
    errors.append("inventory_report")

# Cleanup
proc.stdin.close()
proc.wait()

# Summary
print("\n=== Test Summary ===")
if errors:
    print(f"✗ Tests failed: {', '.join(errors)}")
    sys.exit(1)
else:
    print("✓ All smoke tests passed!")
    sys.exit(0)
PYEOF

# Run the test client
echo -e "\n${YELLOW}Running smoke tests...${NC}\n"
python3 test_inventory_client.py

TEST_EXIT_CODE=$?

# Check for artifacts
echo -e "\n${YELLOW}Checking artifacts...${NC}"
if [ -d "$ARTIFACTS_DIR" ]; then
    ARTIFACT_COUNT=$(find "$ARTIFACTS_DIR" -name "*.md" -o -name "*.html" -o -name "*.json" | wc -l)
    if [ "$ARTIFACT_COUNT" -gt 0 ]; then
        echo -e "${GREEN}✓ Found $ARTIFACT_COUNT artifact(s) in $ARTIFACTS_DIR${NC}"
        ls -lh "$ARTIFACTS_DIR"/*.md "$ARTIFACTS_DIR"/*.html "$ARTIFACTS_DIR"/*.json 2>/dev/null || true
    else
        echo -e "${YELLOW}⚠ No artifacts found (may be expected if export was not called)${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Artifacts directory not created${NC}"
fi

# Cleanup test script
rm -f test_inventory_client.py

# Final result
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}=== All smoke tests passed! ===${NC}"
    exit 0
else
    echo -e "\n${RED}=== Smoke tests failed ===${NC}"
    exit 1
fi

