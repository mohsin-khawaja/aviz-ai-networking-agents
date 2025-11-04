"""Telemetry agent for collecting network device telemetry."""
import random
from typing import Dict, List
from utils.logger import setup_logger

logger = setup_logger(__name__)


def get_port_telemetry() -> dict:
    """
    Simulate SONiC port telemetry metrics.
    
    Returns:
        Dictionary containing port telemetry data
    """
    logger.info("Collecting SONiC port telemetry")
    telemetry = {
        "switch": "sonic-leaf-01",
        "interface": "Ethernet12",
        "rx_bytes": random.randint(10_000, 10_000_000),
        "tx_bytes": random.randint(10_000, 10_000_000),
        "rx_errors": random.randint(0, 10),
        "tx_errors": random.randint(0, 10),
        "utilization": round(random.uniform(0.2, 0.95), 2),
    }
    logger.debug(f"Telemetry collected: {telemetry}")
    return telemetry


def get_network_topology() -> dict:
    """
    Return a mock network topology with multiple device types.
    
    Simulates a multi-vendor network with SONiC, Cisco, FortiGate, and other devices.
    
    Returns:
        Dictionary containing network topology with devices, links, and metadata
    """
    logger.info("Generating network topology")
    topology = {
        "timestamp": "2024-01-15T10:30:00Z",
        "devices": [
            {
                "id": "sonic-leaf-01",
                "type": "SONiC",
                "vendor": "Dell",
                "model": "S5248F-ON",
                "role": "leaf",
                "status": "active",
                "interfaces": [
                    {"name": "Ethernet12", "status": "up", "speed": "25G"},
                    {"name": "Ethernet24", "status": "up", "speed": "100G"}
                ]
            },
            {
                "id": "sonic-spine-01",
                "type": "SONiC",
                "vendor": "Arista",
                "model": "DCS-7280SR3",
                "role": "spine",
                "status": "active",
                "interfaces": [
                    {"name": "Ethernet1/1", "status": "up", "speed": "100G"},
                    {"name": "Ethernet1/2", "status": "up", "speed": "100G"}
                ]
            },
            {
                "id": "cisco-core-01",
                "type": "Cisco",
                "vendor": "Cisco",
                "model": "Nexus 9000",
                "role": "core",
                "status": "active",
                "interfaces": [
                    {"name": "GigabitEthernet0/1", "status": "up", "speed": "10G"},
                    {"name": "GigabitEthernet0/2", "status": "up", "speed": "10G"}
                ]
            },
            {
                "id": "fortigate-fw-01",
                "type": "FortiGate",
                "vendor": "Fortinet",
                "model": "FortiGate 100F",
                "role": "firewall",
                "status": "active",
                "interfaces": [
                    {"name": "port1", "status": "up", "speed": "1G"},
                    {"name": "port2", "status": "up", "speed": "1G"}
                ]
            },
            {
                "id": "arista-leaf-02",
                "type": "EOS",
                "vendor": "Arista",
                "model": "DCS-7050TX3",
                "role": "leaf",
                "status": "active",
                "interfaces": [
                    {"name": "Ethernet1", "status": "up", "speed": "10G"},
                    {"name": "Ethernet2", "status": "up", "speed": "10G"}
                ]
            }
        ],
        "links": [
            {
                "source": "sonic-leaf-01",
                "source_port": "Ethernet24",
                "target": "sonic-spine-01",
                "target_port": "Ethernet1/1",
                "bandwidth": "100G",
                "status": "up"
            },
            {
                "source": "cisco-core-01",
                "source_port": "GigabitEthernet0/1",
                "target": "sonic-spine-01",
                "target_port": "Ethernet1/2",
                "bandwidth": "10G",
                "status": "up"
            },
            {
                "source": "fortigate-fw-01",
                "source_port": "port1",
                "target": "cisco-core-01",
                "target_port": "GigabitEthernet0/2",
                "bandwidth": "1G",
                "status": "up"
            }
        ],
        "statistics": {
            "total_devices": 5,
            "sonic_devices": 2,
            "non_sonic_devices": 3,
            "total_links": 3,
            "active_links": 3
        }
    }
    logger.debug(f"Topology generated with {topology['statistics']['total_devices']} devices")
    return topology

