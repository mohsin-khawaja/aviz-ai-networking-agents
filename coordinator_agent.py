#!/usr/bin/env python3
"""Standalone coordinator agent script for Aviz NCP AI ONE Center.

This script can be run directly to test the coordinator agent without the
full interactive CLI interface.

Usage:
    python coordinator_agent.py
    python coordinator_agent.py "Which VLAN is sonic-leaf-01 on?"
    python coordinator_agent.py "Show devices with rx_errors > 5"
"""
import sys
import json
from agents.coordinator_agent import get_coordinator

def main():
    """Run coordinator agent with command-line query or interactive mode."""
    coordinator = get_coordinator()
    
    if len(sys.argv) > 1:
        # Command-line query mode
        query = " ".join(sys.argv[1:])
        print(f"Query: {query}\n")
        result = coordinator.execute_query(query)
        print("\n" + "=" * 70)
        print("Coordinator Result")
        print("=" * 70)
        print(json.dumps(result, indent=2))
    else:
        # Interactive mode
        print("Aviz Coordinator Agent - Interactive Mode")
        print("Type queries or 'quit' to exit\n")
        
        while True:
            try:
                query = input("> ").strip()
                if not query:
                    continue
                if query.lower() in ["quit", "exit", "q"]:
                    break
                result = coordinator.execute_query(query)
                print("\nSummary:", result.get("summary", "N/A"))
                print("Agents called:", ", ".join(result.get("agents_called", [])))
                print("\nResults:")
                for agent, agent_result in result.get("results", {}).items():
                    print(f"\n  {agent}:")
                    if isinstance(agent_result, dict):
                        print(f"    Query Type: {agent_result.get('query_type', 'N/A')}")
                        print(f"    Summary: {agent_result.get('summary', 'N/A')}")
                        data = agent_result.get("data", {})
                        if isinstance(data, dict) and "device" in data:
                            device = data["device"]
                            print(f"    Device: {device.get('name', 'N/A')}")
                        elif isinstance(data, list):
                            print(f"    Items: {len(data)}")
                        elif isinstance(data, dict):
                            print(f"    Data keys: {list(data.keys())}")
                print()
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    main()

