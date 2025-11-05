"""Data models for inventory management and correlation.

This module defines typed data structures for device inventory, snapshots,
mismatches, and reports using dataclasses for type safety and serialization.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


@dataclass
class VLAN:
    """VLAN information."""
    id: int
    name: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {"id": self.id, "name": self.name}


@dataclass
class Device:
    """Device information model."""
    name: str
    ip: str
    vendor: str
    os: str
    role: str
    region: Optional[str] = None
    vlans: List[VLAN] = field(default_factory=list)
    interfaces: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "name": self.name,
            "ip": self.ip,
            "vendor": self.vendor,
            "os": self.os,
            "role": self.role,
        }
        if self.region:
            result["region"] = self.region
        if self.vlans:
            result["vlans"] = [v.to_dict() for v in self.vlans]
        if self.interfaces:
            result["interfaces"] = self.interfaces
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Device":
        """Create Device from dictionary."""
        vlans = []
        if "vlans" in data:
            for vlan_data in data["vlans"]:
                if isinstance(vlan_data, dict):
                    vlans.append(VLAN(id=vlan_data.get("id", 0), name=vlan_data.get("name", "")))
                elif isinstance(vlan_data, int):
                    vlans.append(VLAN(id=vlan_data, name="unknown"))
        
        return cls(
            name=data.get("name", ""),
            ip=data.get("ip", ""),
            vendor=data.get("vendor", ""),
            os=data.get("os", ""),
            role=data.get("role", ""),
            region=data.get("region"),
            vlans=vlans,
            interfaces=data.get("interfaces")
        )


@dataclass
class InventorySnapshot:
    """Inventory snapshot from a source."""
    devices: List[Device]
    generated_at: datetime
    source: Literal["netbox", "yaml", "merged"] = "yaml"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "devices": [d.to_dict() for d in self.devices],
            "generated_at": self.generated_at.isoformat(),
            "source": self.source
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InventorySnapshot":
        """Create InventorySnapshot from dictionary."""
        devices = [Device.from_dict(d) for d in data.get("devices", [])]
        generated_at_str = data.get("generated_at")
        if isinstance(generated_at_str, str):
            generated_at = datetime.fromisoformat(generated_at_str)
        else:
            generated_at = datetime.now()
        
        return cls(
            devices=devices,
            generated_at=generated_at,
            source=data.get("source", "yaml")
        )


@dataclass
class InventoryMismatch:
    """Inventory mismatch/difference between sources."""
    category: str
    expected: Any
    observed: Any
    device_name: str
    details: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "category": self.category,
            "expected": self.expected,
            "observed": self.observed,
            "device_name": self.device_name,
        }
        if self.details:
            result["details"] = self.details
        return result


@dataclass
class InventoryReport:
    """Inventory validation report."""
    passed: int = 0
    failed: int = 0
    not_run: int = 0
    mismatches: List[InventoryMismatch] = field(default_factory=list)
    groups: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "passed": self.passed,
            "failed": self.failed,
            "not_run": self.not_run,
            "mismatches": [m.to_dict() for m in self.mismatches],
            "groups": self.groups
        }

