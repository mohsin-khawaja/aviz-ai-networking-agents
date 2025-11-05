"""Inventory agent wrapper for coordinator system.

This wraps the existing inventory_agent functions into a class-based interface
for the coordinator system. Also provides access to production inventory tools.
"""
from typing import Dict, Any, Optional
from utils.logger import setup_logger
from agents.inventory_agent import (
    get_device_info,
    list_devices_by_vlan,
    get_vlan_table,
    load_device_inventory,
    load_yaml_inventory,
    load_netbox_inventory,
    merge_inventories,
    group_by,
    detect_mismatches,
    optional_identity_verify
)
from agents.inventory_models import InventoryReport

logger = setup_logger(__name__)


class InventoryAgent:
    """Agent for handling device inventory queries."""
    
    def __init__(self):
        """Initialize the inventory agent."""
        # Ensure inventory is loaded
        try:
            load_device_inventory()
        except Exception as e:
            logger.warning(f"Failed to load device inventory: {e}")
        logger.info("Inventory agent initialized")
    
    def process_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process an inventory-related query.
        
        Args:
            query: Natural language query
            context: Optional conversation context
            
        Returns:
            Dictionary with query result and summary
        """
        query_lower = query.lower()
        
        # Extract VLAN ID if present
        import re
        vlan_match = re.search(r'vlan\s+(\d+)', query_lower)
        if vlan_match:
            vlan_id = int(vlan_match.group(1))
            result = list_devices_by_vlan(vlan_id)
            return {
                "success": True,
                "agent": "inventory",
                "query_type": "vlan_lookup",
                "data": result,
                "summary": f"Found {result.get('count', 0)} device(s) on VLAN {vlan_id}"
            }
        
        # Check for VLAN table request
        if "vlan table" in query_lower or "show vlan" in query_lower:
            result = get_vlan_table()
            return {
                "success": True,
                "agent": "inventory",
                "query_type": "vlan_table",
                "data": result,
                "summary": f"VLAN table with {result.get('total_vlans', 0)} VLANs"
            }
        
        # Extract device name if present
        device_pattern = r'\b(sonic-\S+|nexus-\S+|edgecore-\S+|celtica-\S+|\S+-\d+)\b'
        device_match = re.search(device_pattern, query, re.IGNORECASE)
        if device_match:
            device_name = device_match.group(1)
            result = get_device_info(device_name=device_name)
            if result.get("success"):
                device = result.get("device", {})
                return {
                    "success": True,
                    "agent": "inventory",
                    "query_type": "device_info",
                    "data": result,
                    "summary": f"Device {device_name}: {device.get('role', 'N/A')} role, {len(device.get('vlans', []))} VLAN(s)"
                }
            else:
                return {
                    "success": False,
                    "agent": "inventory",
                    "query_type": "device_info",
                    "data": result,
                    "summary": f"Device {device_name} not found in inventory"
                }
        
        # Check for list all devices queries
        if "list all" in query_lower or "show all" in query_lower:
            if "sonic" in query_lower:
                result = get_device_info(query_type="sonic")
            else:
                result = get_device_info(query_type="all")
            
            count = result.get("count", 0)
            return {
                "success": True,
                "agent": "inventory",
                "query_type": "device_list",
                "data": result,
                "summary": f"Found {count} device(s) in inventory"
            }
        
        # Check for new production inventory queries
        # "Show SONiC leaf switches" or "List SONiC devices"
        if "sonic" in query_lower and ("leaf" in query_lower or "switch" in query_lower or "device" in query_lower):
            yaml_snap = load_yaml_inventory()
            netbox_snap = load_netbox_inventory()
            merged = merge_inventories(yaml_snap, netbox_snap)
            # Filter by OS and role
            devices = [d for d in merged.devices if d.os.lower() == "sonic" and ("leaf" in d.role.lower() if "leaf" in query_lower else True)]
            return {
                "success": True,
                "agent": "inventory",
                "query_type": "device_list",
                "data": {"devices": [d.to_dict() for d in devices], "count": len(devices)},
                "summary": f"Found {len(devices)} SONiC device(s)"
            }
        
        # "Group devices by vendor" or "Show inventory summary"
        if "group" in query_lower and ("vendor" in query_lower or "by vendor" in query_lower):
            yaml_snap = load_yaml_inventory()
            netbox_snap = load_netbox_inventory()
            merged = merge_inventories(yaml_snap, netbox_snap)
            vendor_groups = group_by(merged, "vendor")
            groups_dict = {k: [d.to_dict() for d in v] for k, v in vendor_groups.items()}
            return {
                "success": True,
                "agent": "inventory",
                "query_type": "inventory_summary",
                "data": {"by_vendor": groups_dict},
                "summary": f"Grouped {len(merged.devices)} devices by vendor"
            }
        
        # "Any mismatches between YAML and NetBox?" or "Check mismatches"
        if "mismatch" in query_lower or ("yam" in query_lower and "netbox" in query_lower):
            yaml_snap = load_yaml_inventory()
            netbox_snap = load_netbox_inventory()
            mismatches = detect_mismatches(yaml_snap, netbox_snap)
            return {
                "success": True,
                "agent": "inventory",
                "query_type": "inventory_mismatches",
                "data": {"mismatches": [m.to_dict() for m in mismatches], "count": len(mismatches)},
                "summary": f"Found {len(mismatches)} mismatch(es) between YAML and NetBox"
            }
        
        # "Generate an inventory report" or "Inventory report"
        if "inventory report" in query_lower or ("generate" in query_lower and "report" in query_lower):
            yaml_snap = load_yaml_inventory()
            netbox_snap = load_netbox_inventory()
            merged = merge_inventories(yaml_snap, netbox_snap)
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
            
            export_format = "none"
            if "html" in query_lower:
                export_format = "html"
            elif "markdown" in query_lower or "md" in query_lower:
                export_format = "md"
            elif "json" in query_lower:
                export_format = "json"
            
            return {
                "success": True,
                "agent": "inventory",
                "query_type": "inventory_report",
                "data": {
                    "snapshot": merged.to_dict(),
                    "report": report.to_dict(),
                    "export_format": export_format
                },
                "summary": f"Inventory report: {len(merged.devices)} devices, {len(mismatches)} mismatches"
            }
        
        # Default: return all devices
        result = get_device_info(query_type="all")
        return {
            "success": True,
            "agent": "inventory",
            "query_type": "device_list",
            "data": result,
            "summary": f"Retrieved {result.get('count', 0)} device(s) from inventory"
        }

