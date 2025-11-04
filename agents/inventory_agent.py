"""Device inventory agent for loading and querying YAML-based device metadata.

This module provides tools for loading device inventory from YAML files and
querying device information, VLANs, and device lists based on various criteria.
"""
import yaml
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from utils.logger import setup_logger
# Resolve data path helper
def resolve_data_path(filename: str) -> str:
    """Resolve path to data file, checking multiple locations."""
    from pathlib import Path
    # Check current directory
    current = Path(filename)
    if current.exists():
        return str(current)
    # Check data/ directory
    data_dir = Path("data") / filename
    if data_dir.exists():
        return str(data_dir)
    # Check parent data/ directory
    parent_data = Path(__file__).parent.parent / "data" / filename
    if parent_data.exists():
        return str(parent_data)
    # Return default path
    return str(Path("data") / filename)

logger = setup_logger(__name__)

# Global cache for device inventory
_devices_data: Optional[Dict[str, Any]] = None
_devices_list: Optional[List[Dict[str, Any]]] = None


def load_device_inventory(yaml_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load device inventory from YAML file.
    
    Args:
        yaml_path: Path to devices.yaml file (defaults to data/devices.yaml)
        
    Returns:
        Dictionary containing device inventory data
        
    Raises:
        FileNotFoundError: If YAML file doesn't exist
        yaml.YAMLError: If YAML file is malformed
    """
    global _devices_data, _devices_list
    
    if yaml_path is None:
        yaml_path = resolve_data_path("devices.yaml")
    
    yaml_file = Path(yaml_path)
    if not yaml_file.exists():
        raise FileNotFoundError(f"Device inventory file not found: {yaml_path}")
    
    logger.info(f"Loading device inventory from: {yaml_path}")
    
    try:
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)
        
        if not data or "devices" not in data:
            logger.warning("Device inventory YAML missing 'devices' key")
            data = {"devices": []}
        
        _devices_data = data
        _devices_list = data.get("devices", [])
        
        logger.info(f"Loaded {len(_devices_list)} devices from inventory")
        return data
    
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading device inventory: {e}")
        raise


def get_device_info(device_name: Optional[str] = None, query_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Get device information from inventory.
    
    Args:
        device_name: Name of the device to query (optional, returns all if not provided)
        query_type: Type of query - "all", "basic", "vlans", "by_role", "by_vendor", "by_os" (optional)
        
    Returns:
        Dictionary containing device information or list of devices
    """
    global _devices_list
    
    # Load inventory if not already loaded
    if _devices_list is None:
        try:
            load_device_inventory()
        except Exception as e:
            logger.error(f"Failed to load device inventory: {e}")
            return {
                "error": "Failed to load device inventory",
                "message": str(e),
                "devices": []
            }
    
    result = {
        "success": True,
        "devices": []
    }
    
    # If device_name is provided, find specific device
    if device_name:
        device = None
        for d in _devices_list:
            if d.get("name", "").lower() == device_name.lower():
                device = d.copy()
                break
        
        if device:
            result["device"] = device
            result["devices"] = [device]
        else:
            result["success"] = False
            result["error"] = f"Device '{device_name}' not found in inventory"
            return result
    
    # If query_type is specified, filter devices
    elif query_type:
        query_type_lower = query_type.lower()
        
        if query_type_lower == "all":
            result["devices"] = _devices_list.copy()
        elif query_type_lower in ["sonic", "sonic devices"]:
            result["devices"] = [d for d in _devices_list if d.get("os", "").lower() == "sonic"]
        elif query_type_lower in ["by_role", "role"]:
            # Group by role
            roles = {}
            for d in _devices_list:
                role = d.get("role", "unknown")
                if role not in roles:
                    roles[role] = []
                roles[role].append(d)
            result["devices"] = _devices_list.copy()
            result["grouped_by_role"] = roles
        elif query_type_lower in ["by_vendor", "vendor"]:
            # Group by vendor
            vendors = {}
            for d in _devices_list:
                vendor = d.get("vendor", "unknown")
                if vendor not in vendors:
                    vendors[vendor] = []
                vendors[vendor].append(d)
            result["devices"] = _devices_list.copy()
            result["grouped_by_vendor"] = vendors
        elif query_type_lower in ["by_os", "os"]:
            # Group by OS
            os_types = {}
            for d in _devices_list:
                os_type = d.get("os", "unknown")
                if os_type not in os_types:
                    os_types[os_type] = []
                os_types[os_type].append(d)
            result["devices"] = _devices_list.copy()
            result["grouped_by_os"] = os_types
        else:
            result["devices"] = _devices_list.copy()
    else:
        # Return all devices if no filter specified
        result["devices"] = _devices_list.copy()
    
    result["count"] = len(result["devices"])
    return result


def list_devices_by_vlan(vlan_id: int) -> Dict[str, Any]:
    """
    Find all devices connected to a given VLAN ID.
    
    Args:
        vlan_id: VLAN ID to search for
        
    Returns:
        Dictionary containing list of devices with that VLAN and their VLAN details
    """
    global _devices_list
    
    # Load inventory if not already loaded
    if _devices_list is None:
        try:
            load_device_inventory()
        except Exception as e:
            logger.error(f"Failed to load device inventory: {e}")
            return {
                "error": "Failed to load device inventory",
                "message": str(e),
                "vlan_id": vlan_id,
                "devices": []
            }
    
    matching_devices = []
    
    for device in _devices_list:
        vlans = device.get("vlans", [])
        device_vlan_info = None
        
        # Check if device has this VLAN
        for vlan in vlans:
            if isinstance(vlan, dict):
                if vlan.get("id") == vlan_id:
                    device_vlan_info = vlan
                    break
            elif isinstance(vlan, int) and vlan == vlan_id:
                device_vlan_info = {"id": vlan_id, "name": "unknown"}
                break
        
        if device_vlan_info:
            device_info = {
                "name": device.get("name"),
                "ip": device.get("ip"),
                "vendor": device.get("vendor"),
                "os": device.get("os"),
                "role": device.get("role"),
                "vlan": device_vlan_info
            }
            matching_devices.append(device_info)
    
    return {
        "vlan_id": vlan_id,
        "devices": matching_devices,
        "count": len(matching_devices)
    }


def get_vlan_table() -> Dict[str, Any]:
    """
    Generate a VLAN table showing all VLANs and the devices on each VLAN.
    
    Returns:
        Dictionary containing VLAN table data
    """
    global _devices_list
    
    # Load inventory if not already loaded
    if _devices_list is None:
        try:
            load_device_inventory()
        except Exception as e:
            logger.error(f"Failed to load device inventory: {e}")
            return {
                "error": "Failed to load device inventory",
                "message": str(e),
                "vlan_table": []
            }
    
    vlan_map = {}  # vlan_id -> list of devices
    
    for device in _devices_list:
        device_name = device.get("name", "unknown")
        vlans = device.get("vlans", [])
        
        for vlan in vlans:
            if isinstance(vlan, dict):
                vlan_id = vlan.get("id")
                vlan_name = vlan.get("name", "unknown")
            elif isinstance(vlan, int):
                vlan_id = vlan
                vlan_name = "unknown"
            else:
                continue
            
            if vlan_id not in vlan_map:
                vlan_map[vlan_id] = {
                    "vlan_id": vlan_id,
                    "vlan_name": vlan_name,
                    "devices": []
                }
            
            vlan_map[vlan_id]["devices"].append({
                "name": device_name,
                "ip": device.get("ip"),
                "role": device.get("role")
            })
    
    # Convert to list sorted by VLAN ID
    vlan_table = sorted(vlan_map.values(), key=lambda x: x["vlan_id"])
    
    return {
        "vlan_table": vlan_table,
        "total_vlans": len(vlan_table),
        "total_devices": len(_devices_list)
    }

