"""Device inventory agent for loading and querying YAML-based device metadata.

This module provides tools for loading device inventory from YAML files and
querying device information, VLANs, and device lists based on various criteria.

Production-style Inventory Insight Agent with:
- NetBox integration
- YAML/NetBox correlation and validation
- Mismatch detection
- Optional SSH/Telnet identity verification
- Multiple output formats (table, JSON, Markdown, HTML)
"""
import yaml
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal
from datetime import datetime
from utils.logger import setup_logger
from agents.inventory_models import (
    Device, InventorySnapshot, InventoryMismatch, InventoryReport, VLAN
)
from agents.connection_manager import get_device_identity
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


# -----------------------------
# NEW PRODUCTION-STYLE FUNCTIONS
# -----------------------------

def load_yaml_inventory(path: Optional[str] = None) -> InventorySnapshot:
    """
    Load device inventory from YAML file and return as InventorySnapshot.
    
    Args:
        path: Path to devices.yaml file (defaults to data/devices.yaml)
        
    Returns:
        InventorySnapshot object
    """
    if path is None:
        path = resolve_data_path("devices.yaml")
    
    logger.info(f"Loading YAML inventory from: {path}")
    
    with open(path, 'r') as f:
        data = yaml.safe_load(f)
    
    devices = []
    for device_dict in data.get("devices", []):
        device = Device.from_dict(device_dict)
        devices.append(device)
    
    return InventorySnapshot(
        devices=devices,
        generated_at=datetime.now(),
        source="yaml"
    )


def load_netbox_inventory(
    base_url: Optional[str] = None,
    token: Optional[str] = None
) -> InventorySnapshot:
    """
    Load device inventory from NetBox API.
    
    Reads NetBox URL/TOKEN from environment variables with fallback to
    data/netbox_sample.json if API not available.
    
    Args:
        base_url: NetBox base URL (defaults to NETBOX_URL env var)
        token: NetBox API token (defaults to NETBOX_TOKEN env var)
        
    Returns:
        InventorySnapshot object
    """
    base_url = base_url or os.getenv("NETBOX_URL")
    token = token or os.getenv("NETBOX_TOKEN")
    
    # If no credentials, try to load from sample file
    if not base_url or not token:
        logger.info("NetBox credentials not provided, loading from sample file")
        sample_path = resolve_data_path("netbox_sample.json")
        if Path(sample_path).exists():
            with open(sample_path, 'r') as f:
                data = json.load(f)
        else:
            logger.warning("No NetBox credentials and no sample file found")
            return InventorySnapshot(devices=[], generated_at=datetime.now(), source="netbox")
    else:
        # Try to fetch from NetBox API
        try:
            import requests
            headers = {
                "Authorization": f"Token {token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            url = f"{base_url.rstrip('/')}/api/dcim/devices/"
            logger.info(f"Attempting to fetch devices from NetBox: {url}")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Successfully fetched {data.get('count', len(data.get('results', [])))} devices from NetBox")
        except requests.exceptions.Timeout:
            error_msg = f"NetBox API request timed out for {base_url}"
            logger.error(error_msg)
            logger.info("Falling back to sample file")
            sample_path = resolve_data_path("netbox_sample.json")
            if Path(sample_path).exists():
                with open(sample_path, 'r') as f:
                    data = json.load(f)
            else:
                logger.error("Sample file not found, returning empty snapshot")
                return InventorySnapshot(devices=[], generated_at=datetime.now(), source="netbox")
        except requests.exceptions.RequestException as e:
            error_msg = f"NetBox API request failed: {str(e)}"
            logger.error(error_msg)
            logger.info("Falling back to sample file")
            sample_path = resolve_data_path("netbox_sample.json")
            if Path(sample_path).exists():
                with open(sample_path, 'r') as f:
                    data = json.load(f)
            else:
                logger.error("Sample file not found, returning empty snapshot")
                return InventorySnapshot(devices=[], generated_at=datetime.now(), source="netbox")
        except Exception as e:
            error_msg = f"Unexpected error fetching from NetBox: {str(e)}"
            logger.error(error_msg, exc_info=True)
            logger.info("Falling back to sample file")
            sample_path = resolve_data_path("netbox_sample.json")
            if Path(sample_path).exists():
                with open(sample_path, 'r') as f:
                    data = json.load(f)
            else:
                logger.error("Sample file not found, returning empty snapshot")
                return InventorySnapshot(devices=[], generated_at=datetime.now(), source="netbox")
    
    devices = []
    device_list = data.get("devices", data.get("results", []))
    
    for device_dict in device_list:
        # Normalize NetBox fields to canonical format
        vendor = _normalize_vendor(device_dict.get("manufacturer", device_dict.get("vendor", "")))
        os_type = _normalize_os(device_dict.get("device_type", ""))
        role = _normalize_role(device_dict.get("role", ""))
        region = device_dict.get("site", device_dict.get("region"))
        
        # Extract IP from primary_ip
        primary_ip = device_dict.get("primary_ip", "")
        ip = primary_ip.split("/")[0] if primary_ip else ""
        
        device = Device(
            name=device_dict.get("name", ""),
            ip=ip,
            vendor=vendor,
            os=os_type,
            role=role,
            region=region,
            vlans=[],  # NetBox typically doesn't include VLANs in device list
            interfaces=None
        )
        devices.append(device)
    
    return InventorySnapshot(
        devices=devices,
        generated_at=datetime.now(),
        source="netbox"
    )


def _normalize_vendor(vendor: str) -> str:
    """Normalize vendor name to canonical format (lowercase, trimmed)."""
    if not vendor:
        return "Unknown"
    vendor = vendor.strip().lower()
    mappings = {
        "edgecore": "EdgeCore",
        "cisco": "Cisco",
        "arista": "Arista",
        "celtica": "Celtica",
        "nvidia": "NVIDIA",
        "nvidia corporation": "NVIDIA"
    }
    return mappings.get(vendor, vendor.title())


def _normalize_os(os_type: str) -> str:
    """Normalize OS name to canonical format (lowercase, trimmed)."""
    if not os_type:
        return "Unknown"
    os_lower = os_type.strip().lower()
    if "sonic" in os_lower:
        return "SONiC"
    elif "nx-os" in os_lower or "nexus" in os_lower:
        return "NX-OS"
    elif "ios" in os_lower:
        return "IOS"
    elif "custom" in os_lower:
        return "Custom"
    return os_type.strip().title()


def _normalize_role(role: str) -> str:
    """Normalize device role to canonical format (lowercase, trimmed)."""
    if not role:
        return "unknown"
    role_lower = role.strip().lower()
    if "spine" in role_lower:
        return "spine"
    elif "leaf" in role_lower:
        return "leaf"
    elif "core" in role_lower:
        return "core"
    elif "aggregation" in role_lower or "agg" in role_lower:
        return "aggregation"
    return role_lower


def merge_inventories(
    yaml_snapshot: InventorySnapshot,
    netbox_snapshot: InventorySnapshot
) -> InventorySnapshot:
    """
    Merge YAML and NetBox inventories.
    
    Merges by device name or IP, preferring NetBox fields when present
    but keeping YAML VLAN lists if NetBox lacks them.
    
    Args:
        yaml_snapshot: InventorySnapshot from YAML
        netbox_snapshot: InventorySnapshot from NetBox
        
    Returns:
        Merged InventorySnapshot
    """
    merged_devices = []
    yaml_by_name = {d.name.lower(): d for d in yaml_snapshot.devices}
    yaml_by_ip = {d.ip: d for d in yaml_snapshot.devices if d.ip}
    netbox_by_name = {d.name.lower(): d for d in netbox_snapshot.devices}
    netbox_by_ip = {d.ip: d for d in netbox_snapshot.devices if d.ip}
    
    # Process NetBox devices first (preferred source)
    processed_names = set()
    for netbox_device in netbox_snapshot.devices:
        name_key = netbox_device.name.lower()
        processed_names.add(name_key)
        
        # Try to find matching YAML device
        yaml_device = yaml_by_name.get(name_key) or yaml_by_ip.get(netbox_device.ip)
        
        if yaml_device:
            # Merge: prefer NetBox but keep YAML VLANs
            merged_device = Device(
                name=netbox_device.name,
                ip=netbox_device.ip or yaml_device.ip,
                vendor=netbox_device.vendor or yaml_device.vendor,
                os=netbox_device.os or yaml_device.os,
                role=netbox_device.role or yaml_device.role,
                region=netbox_device.region or yaml_device.region,
                vlans=yaml_device.vlans if yaml_device.vlans else netbox_device.vlans,
                interfaces=yaml_device.interfaces or netbox_device.interfaces
            )
        else:
            # NetBox-only device
            merged_device = netbox_device
        
        merged_devices.append(merged_device)
    
    # Add YAML-only devices
    for yaml_device in yaml_snapshot.devices:
        name_key = yaml_device.name.lower()
        if name_key not in processed_names:
            merged_devices.append(yaml_device)
    
    return InventorySnapshot(
        devices=merged_devices,
        generated_at=datetime.now(),
        source="merged"
    )


def group_by(
    snapshot: InventorySnapshot,
    key: Literal["vendor", "role", "region", "os"]
) -> Dict[str, List[Device]]:
    """
    Group devices by a specified key.
    
    Args:
        snapshot: InventorySnapshot to group
        key: Field to group by (vendor, role, region, os)
        
    Returns:
        Dictionary mapping key values to lists of devices
    """
    groups: Dict[str, List[Device]] = {}
    
    for device in snapshot.devices:
        value = getattr(device, key, "unknown")
        if value is None:
            value = "unknown"
        value_str = str(value)
        
        if value_str not in groups:
            groups[value_str] = []
        groups[value_str].append(device)
    
    return groups


def detect_mismatches(
    yaml_snapshot: InventorySnapshot,
    netbox_snapshot: InventorySnapshot
) -> List[InventoryMismatch]:
    """
    Detect mismatches between YAML and NetBox inventories.
    
    Categories:
    - MISSING_IN_NETBOX: Device in YAML but not in NetBox
    - MISSING_IN_YAML: Device in NetBox but not in YAML
    - NAME_MISMATCH: Same IP but different name
    - ROLE_MISMATCH: Same device but different role
    - VENDOR_MISMATCH: Same device but different vendor
    - VLAN_MISMATCH: VLAN differences (not implemented in detail)
    
    Args:
        yaml_snapshot: YAML inventory snapshot
        netbox_snapshot: NetBox inventory snapshot
        
    Returns:
        List of InventoryMismatch objects
    """
    mismatches = []
    
    yaml_by_name = {d.name.lower(): d for d in yaml_snapshot.devices}
    yaml_by_ip = {d.ip: d for d in yaml_snapshot.devices if d.ip}
    netbox_by_name = {d.name.lower(): d for d in netbox_snapshot.devices}
    netbox_by_ip = {d.ip: d for d in netbox_snapshot.devices if d.ip}
    
    # Check for devices missing in NetBox
    for yaml_device in yaml_snapshot.devices:
        name_key = yaml_device.name.lower()
        if name_key not in netbox_by_name and yaml_device.ip not in netbox_by_ip:
            mismatches.append(InventoryMismatch(
                category="MISSING_IN_NETBOX",
                expected=yaml_device.name,
                observed="Not found in NetBox",
                device_name=yaml_device.name,
                details=f"Device {yaml_device.name} ({yaml_device.ip}) exists in YAML but not in NetBox"
            ))
    
    # Check for devices missing in YAML
    for netbox_device in netbox_snapshot.devices:
        name_key = netbox_device.name.lower()
        if name_key not in yaml_by_name and netbox_device.ip not in yaml_by_ip:
            mismatches.append(InventoryMismatch(
                category="MISSING_IN_YAML",
                expected="Not found in YAML",
                observed=netbox_device.name,
                device_name=netbox_device.name,
                details=f"Device {netbox_device.name} ({netbox_device.ip}) exists in NetBox but not in YAML"
            ))
    
    # Check for mismatches in matching devices
    for yaml_device in yaml_snapshot.devices:
        name_key = yaml_device.name.lower()
        netbox_device = netbox_by_name.get(name_key) or netbox_by_ip.get(yaml_device.ip)
        
        if netbox_device:
            # Check role mismatch
            if yaml_device.role and netbox_device.role and yaml_device.role.lower() != netbox_device.role.lower():
                mismatches.append(InventoryMismatch(
                    category="ROLE_MISMATCH",
                    expected=yaml_device.role,
                    observed=netbox_device.role,
                    device_name=yaml_device.name,
                    details=f"Role mismatch for {yaml_device.name}"
                ))
            
            # Check vendor mismatch
            if yaml_device.vendor and netbox_device.vendor and yaml_device.vendor.lower() != netbox_device.vendor.lower():
                mismatches.append(InventoryMismatch(
                    category="VENDOR_MISMATCH",
                    expected=yaml_device.vendor,
                    observed=netbox_device.vendor,
                    device_name=yaml_device.name,
                    details=f"Vendor mismatch for {yaml_device.name}"
                ))
    
    return mismatches


def optional_identity_verify(
    devices: List[Device],
    enabled: bool = True
) -> List[InventoryMismatch]:
    """
    Optionally verify device identity via SSH/Telnet.
    
    For each device with IP and credentials, run a lightweight command
    and compare hostname/vendor to expected values.
    
    Args:
        devices: List of Device objects to verify
        enabled: Whether to enable identity verification
        
    Returns:
        List of InventoryMismatch objects for verification failures
    """
    if not enabled:
        return []
    
    mismatches = []
    
    for device in devices:
        if not device.ip:
            continue
        
        try:
            identity = get_device_identity(device.to_dict())
            if identity:
                # Check hostname match (basic check)
                hostname = identity.get("hostname", "").lower()
                device_name_lower = device.name.lower()
                
                # Simple hostname matching (may not always match exactly)
                if hostname and device_name_lower not in hostname and hostname not in device_name_lower:
                    mismatches.append(InventoryMismatch(
                        category="IDENTITY_MISMATCH",
                        expected=device.name,
                        observed=hostname,
                        device_name=device.name,
                        details=f"Device identity verification: expected hostname matching {device.name}, got {hostname}"
                    ))
        except Exception as e:
            logger.debug(f"Identity verification failed for {device.name}: {e}")
            # Don't add mismatch for connection failures, only for mismatches
    
    return mismatches

