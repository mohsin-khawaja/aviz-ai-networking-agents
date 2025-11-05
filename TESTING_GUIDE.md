# Testing Guide for Inventory Insight Agent

## Available Agents

### 1. **main_agent.py** (Recommended for Testing)
Interactive multi-agent coordinator with CLI commands and natural language support.

**Run:**
```bash
python main_agent.py
```

### 2. **coordinator_agent.py**
Standalone coordinator agent (simpler output, good for testing routing).

**Run:**
```bash
python coordinator_agent.py
# or with a query:
python coordinator_agent.py "Show SONiC leaf switches"
```

### 3. **mcp_server.py**
MCP server (usually runs in background, needed for MCP tool calls).

**Run:**
```bash
python mcp_server.py
```

---

## Testing New Inventory Features

### Test 1: CLI Commands (Direct)

Run these directly from command line:

```bash
# List devices with filtering
python main_agent.py inventory list --by vendor --value EdgeCore --format table
python main_agent.py inventory list --by os --value SONiC --format json
python main_agent.py inventory list --by role --value leaf --format markdown
python main_agent.py inventory list --by vlan_id --value 103 --format table

# Get inventory summary
python main_agent.py inventory summary --format table
python main_agent.py inventory summary --format markdown
python main_agent.py inventory summary --format json

# Check for mismatches
python main_agent.py inventory mismatches --format table
python main_agent.py inventory mismatches --identity-check --format json

# Generate reports
python main_agent.py inventory report --export html
python main_agent.py inventory report --export md
python main_agent.py inventory report --export json
python main_agent.py inventory report  # Just prints summary
```

### Test 2: Interactive CLI Commands

Run `python main_agent.py` and type these commands:

```
> inventory list --by vendor --value Cisco --format table
> inventory summary --format markdown
> inventory mismatches --format table
> inventory report --export html
```

### Test 3: Natural Language Queries (Coordinator)

Run `python main_agent.py` and try these natural language queries:

#### Basic Inventory Queries:
```
> List all devices
> Show all SONiC devices
> List devices by vendor
> Show inventory summary
```

#### SONiC Leaf Switches (New Feature):
```
> Show SONiC leaf switches
> List SONiC leaf devices
> Show me all SONiC switches
```

#### Grouping by Vendor (New Feature):
```
> Group devices by vendor
> Show devices grouped by vendor
> What vendors do we have?
```

#### Mismatch Detection (New Feature):
```
> Any mismatches between YAML and NetBox?
> Check for inventory mismatches
> Show mismatches between YAML and NetBox
> Are there any discrepancies?
```

#### Inventory Reports (New Feature):
```
> Generate an inventory report
> Create inventory report in HTML
> Generate inventory report in markdown
> Show me an inventory report in JSON
```

### Test 4: Coordinator Agent (Simpler Output)

Run `python coordinator_agent.py` and try:

```bash
# Command line mode
python coordinator_agent.py "Show SONiC leaf switches"
python coordinator_agent.py "Group devices by vendor"
python coordinator_agent.py "Any mismatches between YAML and NetBox?"
python coordinator_agent.py "Generate an inventory report in HTML"

# Interactive mode
python coordinator_agent.py
> Show SONiC leaf switches
> Group devices by vendor
> Check mismatches
```

---

## Expected Outputs

### CLI Commands Output:

**Table format** - Nice tabular output with device information
```
+------------------+-------------+-----------+--------+--------+
| name             | ip          | vendor    | os     | role   |
+==================+=============+===========+========+========+
| sonic-leaf-01    | 10.20.11.207| EdgeCore  | SONiC  | leaf   |
+------------------+-------------+-----------+--------+--------+
```

**JSON format** - Structured JSON data
```json
[
  {
    "name": "sonic-leaf-01",
    "ip": "10.20.11.207",
    "vendor": "EdgeCore",
    "os": "SONiC",
    "role": "leaf",
    "vlans": [{"id": 101, "name": "management"}, ...]
  }
]
```

**Markdown format** - Markdown-formatted report
```markdown
# Inventory Report
**Generated:** 2024-01-15 10:30:00
**Source:** merged
...
```

### Natural Language Queries Output:

The coordinator will route queries and show:
- Which agents were called
- Summary of results
- Formatted tables or data

---

## Quick Test Checklist

✅ **Test CLI Commands:**
- [ ] `inventory list` with different filters
- [ ] `inventory summary` in all formats
- [ ] `inventory mismatches` with and without identity check
- [ ] `inventory report` with different export formats

✅ **Test Natural Language:**
- [ ] "Show SONiC leaf switches"
- [ ] "Group devices by vendor"
- [ ] "Any mismatches between YAML and NetBox?"
- [ ] "Generate an inventory report in HTML"

✅ **Test Output Formats:**
- [ ] Table format (should show nicely formatted tables)
- [ ] JSON format (should show valid JSON)
- [ ] Markdown format (should show markdown text)
- [ ] HTML export (should create file in `artifacts/` directory)

✅ **Test Export:**
- [ ] Check `artifacts/` directory for generated reports
- [ ] Verify HTML file opens in browser
- [ ] Verify Markdown file is readable
- [ ] Verify JSON file is valid

---

## Troubleshooting

**If you get import errors:**
```bash
pip install -r requirements.txt
```

**If MCP tools don't work:**
- Make sure `mcp_server.py` can run (it's used internally)
- Check that data files exist: `data/devices.yaml`, `data/netbox_sample.json`

**If identity check fails:**
- Set environment variables: `SSH_USER`, `SSH_PASS`, `TELNET_USER`, `TELNET_PASS`
- Or just skip `--identity-check` flag (it's optional)

**If NetBox connection fails:**
- The system automatically falls back to `data/netbox_sample.json`
- Set `NETBOX_URL` and `NETBOX_TOKEN` in `.env` for real NetBox access

