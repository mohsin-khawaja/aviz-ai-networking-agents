"""Build validation agent for validating SONiC and non-SONiC build metadata."""
import json
import os
from typing import Dict, List
from utils.logger import setup_logger

logger = setup_logger(__name__)


def validate_build_metadata(build_json_path: str) -> dict:
    """
    Validate SONiC or non-SONiC build JSON files.
    
    This function checks build metadata files for required fields and structure.
    Supports both SONiC and non-SONiC device builds.
    
    Args:
        build_json_path: Path to the build JSON file
        
    Returns:
        Dictionary containing validation results, errors, and warnings
    """
    logger.info(f"Validating build metadata: {build_json_path}")
    
    result = {
        "valid": False,
        "device_type": None,
        "errors": [],
        "warnings": [],
        "metadata": {}
    }
    
    # Check if file exists
    if not os.path.exists(build_json_path):
        result["errors"].append(f"File not found: {build_json_path}")
        logger.error(f"Build file not found: {build_json_path}")
        return result
    
    # Try to load and parse JSON
    try:
        with open(build_json_path, 'r') as f:
            build_data = json.load(f)
    except json.JSONDecodeError as e:
        result["errors"].append(f"Invalid JSON: {str(e)}")
        logger.error(f"JSON decode error: {e}")
        return result
    except Exception as e:
        result["errors"].append(f"Error reading file: {str(e)}")
        logger.error(f"File read error: {e}")
        return result
    
    # Determine device type
    if "sonic" in build_data.get("type", "").lower() or "sonic" in build_data.get("platform", "").lower():
        result["device_type"] = "SONiC"
        required_fields = ["version", "platform", "kernel_version", "build_date"]
    else:
        result["device_type"] = "non-SONiC"
        required_fields = ["vendor", "model", "os_version", "firmware_version"]
    
    # Validate required fields
    missing_fields = []
    for field in required_fields:
        if field not in build_data:
            missing_fields.append(field)
    
    if missing_fields:
        result["errors"].append(f"Missing required fields: {', '.join(missing_fields)}")
        logger.warning(f"Missing required fields: {missing_fields}")
    else:
        result["valid"] = True
        logger.info(f"Build metadata validated successfully for {result['device_type']} device")
    
    # Check for optional but recommended fields
    recommended_fields = ["serial_number", "mac_address", "hostname"]
    for field in recommended_fields:
        if field not in build_data:
            result["warnings"].append(f"Recommended field missing: {field}")
    
    result["metadata"] = build_data
    return result


def create_sample_build_files():
    """
    Create sample build JSON files for testing.
    This is a utility function for development/testing.
    """
    sample_sonic = {
        "type": "SONiC",
        "version": "202311.1",
        "platform": "x86_64-arista_7170_64c",
        "kernel_version": "5.10.0-8-amd64",
        "build_date": "2024-01-10",
        "serial_number": "SN123456789",
        "mac_address": "00:1c:73:aa:bb:cc",
        "hostname": "sonic-leaf-01"
    }
    
    sample_cisco = {
        "vendor": "Cisco",
        "model": "Nexus 9000",
        "os_version": "9.3(7)",
        "firmware_version": "7.0(3)I7(8)",
        "serial_number": "FDO1234ABCD",
        "mac_address": "00:1e:13:dd:ee:ff",
        "hostname": "cisco-core-01"
    }
    
    os.makedirs("sample_builds", exist_ok=True)
    
    with open("sample_builds/sonic_build.json", "w") as f:
        json.dump(sample_sonic, f, indent=2)
    
    with open("sample_builds/cisco_build.json", "w") as f:
        json.dump(sample_cisco, f, indent=2)
    
    logger.info("Sample build files created in sample_builds/")

