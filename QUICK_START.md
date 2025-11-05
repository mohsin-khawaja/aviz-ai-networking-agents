# Quick Start Guide - Running Agent Queries

This guide shows you how to run agent queries and test the new `get_inventory_devices` tool.

## 🚀 Quick Test Options

### Option 1: Test the New Tool Directly (Fastest)

**Run the standalone test script:**
```bash
python test_inventory_devices.py
```

This will:
- Check if NCP SDK is installed
- Check if `.env` file has NETBOX_URL and NETBOX_TOKEN
- Start MCP server automatically
- Call `get_inventory_devices` tool
- Display results in a readable format

**Prerequisites:**
1. Install NCP SDK: `pip install git+https://github.com/Ashok-Aviz/ncp-sdk.git`
2. Create `.env` file with:
   ```
   NETBOX_URL=https://your-netbox-instance.com
   NETBOX_TOKEN=your-api-token-here
   ```

---

### Option 2: Interactive CLI with Natural Language (Recommended)

**Two-terminal setup:**

**Terminal 1 - Start MCP Server:**
```bash
python mcp_server.py
```
Keep this running in the background.

**Terminal 2 - Run Interactive Agent:**
```bash
python main_agent.py
```

Then you can ask questions like:
- `"What devices are in NetBox?"`
- `"Show me the inventory from NetBox"`
- `"List all devices"`
- `"Get device inventory"`

The agent will automatically route to the `get_inventory_devices` tool.

**Or use CLI commands:**
```
inventory list --format table
inventory summary --format json
inventory report --export md
```

---

### Option 3: Full Test Suite

**Run all tests including the new tool:**
```bash
python client_test.py
```

This tests all MCP tools including Test 10 for `get_inventory_devices`.

**Note:** Requires MCP server to be running. The script starts it automatically.

---

### Option 4: Direct MCP Tool Call (Advanced)

**Terminal 1 - Start MCP Server:**
```bash
python mcp_server.py
```

**Terminal 2 - Use Python to call the tool:**
```python
import json
import subprocess
import sys
import time

# Start MCP server
proc = subprocess.Popen(
    [sys.executable, "mcp_server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Initialize connection
init_req = json.dumps({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "1.0.0"}
    }
}) + "\n"

proc.stdin.write(init_req)
proc.stdin.flush()
time.sleep(1)

# Call get_inventory_devices
tool_req = json.dumps({
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "get_inventory_devices",
        "arguments": {}
    }
}) + "\n"

proc.stdin.write(tool_req)
proc.stdin.flush()
time.sleep(1)

# Read response
response = proc.stdout.readline()
print(json.dumps(json.loads(response), indent=2))
```

---

## 📋 File Summary

| File | Purpose | When to Use |
|------|---------|-------------|
| `test_inventory_devices.py` | Quick test of new tool | Fastest way to test `get_inventory_devices` |
| `main_agent.py` | Interactive CLI with natural language | Best for exploring all features interactively |
| `client_test.py` | Full test suite | Testing all tools systematically |
| `mcp_server.py` | MCP server | Must be running for any tool calls |
| `coordinator_agent.py` | Standalone coordinator | Alternative to main_agent.py |

---

## 🔧 Setup Checklist

Before running queries, ensure:

- [ ] NCP SDK installed: `pip install git+https://github.com/Ashok-Aviz/ncp-sdk.git`
- [ ] `.env` file exists with `NETBOX_URL` and `NETBOX_TOKEN`
- [ ] Virtual environment activated (if using one)
- [ ] Dependencies installed: `pip install -r requirements.txt`

---

## 💡 Example Queries for main_agent.py

Once `main_agent.py` is running, try these:

**Inventory queries:**
- "Get all devices from NetBox"
- "Show me the device inventory"
- "What devices are in the inventory?"
- "List devices by vendor"

**Natural language:**
- "Which devices are Cisco switches?"
- "Show me all leaf switches"
- "What's the inventory status?"

The coordinator agent will automatically route these to the appropriate tools, including the new `get_inventory_devices` tool.

---

## 🐛 Troubleshooting

**Error: "ncp_sdk not installed"**
```bash
pip install git+https://github.com/Ashok-Aviz/ncp-sdk.git
```

**Error: "NETBOX_URL not set"**
Create `.env` file:
```bash
NETBOX_URL=https://your-netbox-instance.com
NETBOX_TOKEN=your-token-here
```

**Error: "MCP server not responding"**
- Make sure `mcp_server.py` is running in another terminal
- Check for port conflicts
- Verify Python version (3.10+)

**Tool returns empty results**
- Verify NetBox credentials are correct
- Check NetBox API token permissions
- Ensure NetBox instance is accessible

