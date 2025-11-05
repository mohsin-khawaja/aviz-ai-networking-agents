"""Rendering utilities for inventory data in multiple formats.

This module provides functions to render inventory data as tables, JSON,
Markdown, and HTML reports.
"""
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from tabulate import tabulate
    TABULATE_AVAILABLE = True
except ImportError:
    TABULATE_AVAILABLE = False

try:
    from jinja2 import Template, Environment, FileSystemLoader
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

from agents.inventory_models import Device, InventorySnapshot, InventoryReport


def to_table(
    devices: List[Device],
    columns: Optional[List[str]] = None,
    tablefmt: str = "grid"
) -> str:
    """
    Render devices as a formatted table.
    
    Args:
        devices: List of Device objects
        columns: List of column names to include (default: all)
        tablefmt: Table format (grid, github, markdown, plain)
        
    Returns:
        Formatted table string
    """
    if not devices:
        return "No devices found"
    
    if not TABULATE_AVAILABLE:
        # Simple fallback table
        return _simple_table(devices, columns)
    
    # Default columns
    if columns is None:
        columns = ["name", "ip", "vendor", "os", "role", "vlans"]
    
    # Build table data
    table_data = []
    for device in devices:
        row = []
        for col in columns:
            if col == "vlans":
                vlans_str = ", ".join([f"VLAN {v.id}" for v in device.vlans])
                row.append(vlans_str[:50] + ("..." if len(vlans_str) > 50 else ""))
            elif col == "interfaces" and device.interfaces:
                row.append(", ".join(device.interfaces[:3]))
            else:
                value = getattr(device, col, "")
                row.append(str(value) if value is not None else "")
        table_data.append(row)
    
    return tabulate(table_data, headers=columns, tablefmt=tablefmt)


def _simple_table(devices: List[Device], columns: Optional[List[str]]) -> str:
    """Simple table formatter when tabulate is not available."""
    if columns is None:
        columns = ["name", "ip", "vendor", "os", "role"]
    
    # Calculate column widths
    col_widths = [len(str(col)) for col in columns]
    for device in devices:
        for i, col in enumerate(columns):
            if col == "vlans":
                value = ", ".join([f"VLAN {v.id}" for v in device.vlans])
            else:
                value = str(getattr(device, col, ""))
            col_widths[i] = max(col_widths[i], len(value))
    
    # Build table
    lines = []
    header_line = " | ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(columns))
    lines.append(header_line)
    lines.append("-" * len(header_line))
    
    for device in devices:
        row = []
        for col in columns:
            if col == "vlans":
                value = ", ".join([f"VLAN {v.id}" for v in device.vlans])
            else:
                value = str(getattr(device, col, ""))
            row.append(value.ljust(col_widths[columns.index(col)]))
        lines.append(" | ".join(row))
    
    return "\n".join(lines)


def to_json(obj: Any, indent: int = 2, sort_keys: bool = True) -> str:
    """
    Convert object to stable JSON string.
    
    Args:
        obj: Object to serialize (can be dict, list, or model with to_dict())
        indent: JSON indentation (default: 2)
        sort_keys: Whether to sort dictionary keys (default: True)
        
    Returns:
        JSON string
    """
    # Handle model objects with to_dict()
    if hasattr(obj, "to_dict"):
        obj = obj.to_dict()
    
    return json.dumps(obj, indent=indent, sort_keys=sort_keys, default=str)


def to_markdown_report(
    snapshot: InventorySnapshot,
    report: InventoryReport,
    include_mismatches: bool = True
) -> str:
    """
    Generate a Markdown report from inventory snapshot and validation report.
    
    Args:
        snapshot: InventorySnapshot object
        report: InventoryReport object
        include_mismatches: Whether to include mismatch details
        
    Returns:
        Markdown-formatted report string
    """
    lines = []
    lines.append("# Inventory Report")
    lines.append("")
    lines.append(f"**Generated:** {snapshot.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Source:** {snapshot.source}")
    lines.append("")
    
    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Devices:** {len(snapshot.devices)}")
    lines.append(f"- **Validation Passed:** {report.passed}")
    lines.append(f"- **Validation Failed:** {report.failed}")
    lines.append(f"- **Not Run:** {report.not_run}")
    lines.append("")
    
    # Groupings
    if report.groups:
        lines.append("## Device Groupings")
        lines.append("")
        for group_type, group_data in report.groups.items():
            if isinstance(group_data, dict):
                lines.append(f"### By {group_type.title()}")
                lines.append("")
                for key, devices in group_data.items():
                    if isinstance(devices, list):
                        lines.append(f"- **{key}:** {len(devices)} device(s)")
                    else:
                        lines.append(f"- **{key}:** {devices}")
                lines.append("")
    
    # Mismatches
    if include_mismatches and report.mismatches:
        lines.append("## Mismatches")
        lines.append("")
        lines.append("| Device | Category | Expected | Observed | Details |")
        lines.append("|--------|----------|----------|----------|---------|")
        for mismatch in report.mismatches:
            details = mismatch.details or ""
            lines.append(
                f"| {mismatch.device_name} | {mismatch.category} | "
                f"{mismatch.expected} | {mismatch.observed} | {details} |"
            )
        lines.append("")
    
    # Device List
    lines.append("## Device Inventory")
    lines.append("")
    lines.append("| Name | IP | Vendor | OS | Role | VLANs |")
    lines.append("|------|----|----|----|----|----|")
    for device in snapshot.devices:
        vlans_str = ", ".join([f"{v.id}" for v in device.vlans[:5]])
        if len(device.vlans) > 5:
            vlans_str += f" +{len(device.vlans)-5} more"
        lines.append(
            f"| {device.name} | {device.ip} | {device.vendor} | "
            f"{device.os} | {device.role} | {vlans_str} |"
        )
    
    return "\n".join(lines)


def to_html_report(markdown: str, title: str = "Inventory Report") -> str:
    """
    Convert Markdown report to HTML using Jinja2 template.
    
    Args:
        markdown: Markdown-formatted report string
        title: Report title
        
    Returns:
        HTML-formatted report string
    """
    if not JINJA2_AVAILABLE:
        # Simple HTML fallback
        html_content = _markdown_to_html(markdown)
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div>{html_content}</div>
</body>
</html>"""
    
    # Try to load template
    try:
        from pathlib import Path
        template_dir = Path(__file__).parent.parent / "templates"
        if template_dir.exists():
            env = Environment(loader=FileSystemLoader(str(template_dir)))
            template = env.get_template("inventory_report.html.j2")
        else:
            # Use inline template
            template = Template(_default_html_template())
        
        # Convert markdown to HTML (simple conversion)
        html_content = _markdown_to_html(markdown)
        
        return template.render(
            title=title,
            content=html_content,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    except Exception as e:
        # Fallback to simple HTML
        html_content = _markdown_to_html(markdown)
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div>{html_content}</div>
</body>
</html>"""


def _markdown_to_html(markdown: str) -> str:
    """Simple Markdown to HTML converter."""
    lines = markdown.split("\n")
    html_lines = []
    in_table = False
    
    for line in lines:
        if line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("|"):
            if not in_table:
                html_lines.append("<table>")
                in_table = True
            # Convert table row
            cells = [cell.strip() for cell in line.split("|")[1:-1]]
            if "---" in line or "---" in "".join(cells):
                html_lines.append("<thead><tr>")
                for cell in cells:
                    html_lines.append(f"<th>{cell}</th>")
                html_lines.append("</tr></thead><tbody>")
            else:
                html_lines.append("<tr>")
                for cell in cells:
                    html_lines.append(f"<td>{cell}</td>")
                html_lines.append("</tr>")
        elif line.strip() == "":
            if in_table:
                html_lines.append("</tbody></table>")
                in_table = False
            html_lines.append("<br>")
        else:
            if in_table:
                html_lines.append("</tbody></table>")
                in_table = False
            # Bold text
            line = line.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
            html_lines.append(f"<p>{line}</p>")
    
    if in_table:
        html_lines.append("</tbody></table>")
    
    return "\n".join(html_lines)


def _default_html_template() -> str:
    """Default Jinja2 template for HTML reports."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            color: #34495e;
            margin-top: 30px;
        }
        h3 {
            color: #7f8c8d;
            margin-top: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }
        th {
            background-color: #3498db;
            color: white;
            font-weight: 600;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        tr:hover {
            background-color: #f1f1f1;
        }
        code {
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #7f8c8d;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ title }}</h1>
        <div class="content">
            {{ content | safe }}
        </div>
        <div class="footer">
            <p>Generated: {{ generated_at }}</p>
        </div>
    </div>
</body>
</html>"""

