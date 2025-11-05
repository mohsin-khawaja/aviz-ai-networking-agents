"""Coordinator agent for multi-agent orchestration in Aviz NCP AI ONE Center framework.

This module implements a coordinator that routes natural language queries to
domain-specific sub-agents and combines their responses into unified insights.
"""
from typing import Dict, List, Optional, Any, Tuple
from utils.logger import setup_logger

logger = setup_logger(__name__)


class CoordinatorAgent:
    """
    Coordinator agent that routes queries to domain-specific sub-agents.
    
    This agent implements the AI ONE Center pattern of multi-agent coordination,
    where different agents handle different network domains (Inventory, Telemetry,
    Config, Ticketing) and the coordinator orchestrates cross-domain queries.
    """
    
    def __init__(self):
        """Initialize the coordinator with sub-agent registry."""
        self.sub_agents = {}
        self._register_sub_agents()
        logger.info("Coordinator agent initialized with sub-agents")
    
    def _register_sub_agents(self):
        """Register all available sub-agents."""
        from agents.inventory_agent_wrapper import InventoryAgent
        from agents.telemetry_agent_wrapper import TelemetryAgent
        from agents.config_agent import ConfigAgent
        from agents.ticketing_agent import TicketingAgent
        
        self.sub_agents = {
            "inventory": InventoryAgent(),
            "telemetry": TelemetryAgent(),
            "config": ConfigAgent(),
            "ticketing": TicketingAgent()
        }
        
        logger.info(f"Registered {len(self.sub_agents)} sub-agents: {list(self.sub_agents.keys())}")
    
    def route_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Determine which sub-agent(s) should handle a query.
        
        Uses intent parsing to identify which domains are relevant to the query.
        Returns a list of agent names that should be invoked.
        
        Args:
            query: Natural language query from user
            context: Optional context from previous queries
            
        Returns:
            List of sub-agent names to invoke
        """
        query_lower = query.lower()
        agents_to_call = []
        
        # Inventory-related keywords
        inventory_keywords = [
            "vlan", "device", "inventory", "which device", "list devices",
            "device info", "show device", "device name", "sonic", "nexus",
            "edgecore", "celtica", "nvidia", "role", "vendor", "os",
            "mismatch", "netbox", "yam", "group devices", "inventory summary",
            "inventory report", "generate report", "sonic leaf", "sonic switch"
        ]
        
        # Telemetry-related keywords
        telemetry_keywords = [
            "telemetry", "utilization", "rx_errors", "tx_errors", "rx_bytes",
            "tx_bytes", "bandwidth", "traffic", "interface status", "port",
            "link health", "errors", "cpu", "memory", "high usage"
        ]
        
        # Config-related keywords
        config_keywords = [
            "config", "configuration", "firmware", "version", "build",
            "compliance", "drift", "outdated", "baseline", "validate"
        ]
        
        # Ticketing-related keywords
        ticketing_keywords = [
            "ticket", "servicenow", "zendesk", "incident", "open tickets",
            "priority", "high priority", "critical", "assigned", "status"
        ]
        
        # Route to appropriate agents
        if any(keyword in query_lower for keyword in inventory_keywords):
            agents_to_call.append("inventory")
        
        if any(keyword in query_lower for keyword in telemetry_keywords):
            agents_to_call.append("telemetry")
        
        if any(keyword in query_lower for keyword in config_keywords):
            agents_to_call.append("config")
        
        if any(keyword in query_lower for keyword in ticketing_keywords):
            agents_to_call.append("ticketing")
        
        # If no specific domain identified, try to infer from device names
        if not agents_to_call:
            # Check for device names - likely inventory query
            import re
            device_pattern = r'\b(sonic-\S+|nexus-\S+|edgecore-\S+|celtica-\S+|\S+-\d+)\b'
            if re.search(device_pattern, query, re.IGNORECASE):
                agents_to_call.append("inventory")
            
            # Check for error/health terms - likely telemetry
            if any(term in query_lower for term in ["error", "health", "status", "show"]):
                agents_to_call.append("telemetry")
        
        # Default to inventory if still nothing found
        if not agents_to_call:
            agents_to_call.append("inventory")
        
        logger.info(f"[Coordinator] Routing query to agents: {agents_to_call}")
        return agents_to_call
    
    def execute_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a query by routing to appropriate sub-agents and combining results.
        
        Args:
            query: Natural language query
            context: Optional context from conversation history
            
        Returns:
            Dictionary containing:
            - agents_called: List of agents that were invoked
            - results: Dictionary mapping agent names to their results
            - summary: Human-readable summary of the response
            - structured_data: Combined structured data from all agents
        """
        logger.info(f"[Coordinator] Processing query: {query[:100]}")
        
        # Route query to appropriate agents
        agents_to_call = self.route_query(query, context)
        
        results = {}
        errors = {}
        
        # Execute each agent in parallel (simulated)
        for agent_name in agents_to_call:
            if agent_name not in self.sub_agents:
                logger.warning(f"[Coordinator] Unknown agent: {agent_name}")
                errors[agent_name] = f"Agent {agent_name} not found"
                continue
            
            try:
                agent = self.sub_agents[agent_name]
                logger.debug(f"[Coordinator] Invoking {agent_name} agent")
                result = agent.process_query(query, context)
                results[agent_name] = result
            except Exception as e:
                logger.error(f"[Coordinator] Error in {agent_name} agent: {e}", exc_info=True)
                errors[agent_name] = str(e)
                results[agent_name] = {
                    "error": str(e),
                    "success": False
                }
        
        # Combine results and generate summary
        summary = self._generate_summary(query, results, errors)
        structured_data = self._combine_results(results)
        
        return {
            "query": query,
            "agents_called": agents_to_call,
            "results": results,
            "errors": errors,
            "summary": summary,
            "structured_data": structured_data,
            "success": len(errors) == 0
        }
    
    def _generate_summary(
        self,
        query: str,
        results: Dict[str, Any],
        errors: Dict[str, str]
    ) -> str:
        """Generate a human-readable summary from agent results."""
        summary_parts = []
        
        if errors:
            summary_parts.append(f"Errors encountered: {len(errors)} agent(s) failed")
        
        for agent_name, result in results.items():
            if agent_name in errors:
                continue
            
            if isinstance(result, dict):
                if "summary" in result:
                    summary_parts.append(f"{agent_name.title()}: {result['summary']}")
                elif "data" in result:
                    data = result["data"]
                    if isinstance(data, list) and len(data) > 0:
                        summary_parts.append(f"{agent_name.title()}: Found {len(data)} item(s)")
                    elif isinstance(data, dict):
                        summary_parts.append(f"{agent_name.title()}: {result.get('summary', 'Data retrieved')}")
        
        if not summary_parts:
            return "No results found"
        
        return ". ".join(summary_parts)
    
    def _combine_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Combine results from multiple agents into unified structure."""
        combined = {
            "devices": [],
            "telemetry": [],
            "config_issues": [],
            "tickets": []
        }
        
        # Extract devices from inventory
        if "inventory" in results:
            inv_result = results["inventory"]
            if isinstance(inv_result, dict) and "data" in inv_result:
                devices = inv_result["data"]
                if isinstance(devices, list):
                    combined["devices"] = devices
                elif isinstance(devices, dict) and "devices" in devices:
                    combined["devices"] = devices["devices"]
        
        # Extract telemetry data
        if "telemetry" in results:
            tel_result = results["telemetry"]
            if isinstance(tel_result, dict) and "data" in tel_result:
                telemetry = tel_result["data"]
                if isinstance(telemetry, list):
                    combined["telemetry"] = telemetry
                elif isinstance(telemetry, dict):
                    combined["telemetry"] = [telemetry]
        
        # Extract config issues
        if "config" in results:
            config_result = results["config"]
            if isinstance(config_result, dict) and "data" in config_result:
                issues = config_result["data"]
                if isinstance(issues, list):
                    combined["config_issues"] = issues
        
        # Extract tickets
        if "ticketing" in results:
            ticket_result = results["ticketing"]
            if isinstance(ticket_result, dict) and "data" in ticket_result:
                tickets = ticket_result["data"]
                if isinstance(tickets, list):
                    combined["tickets"] = tickets
        
        return combined


# Global coordinator instance
_coordinator: Optional[CoordinatorAgent] = None


def get_coordinator() -> CoordinatorAgent:
    """Get or create the global coordinator instance."""
    global _coordinator
    if _coordinator is None:
        _coordinator = CoordinatorAgent()
    return _coordinator

