# Mock Aviz AI Agent

This repository contains a prototype implementation of a **Model Context Protocol (MCP)** server used for testing and developing AI-driven agents within Aviz Networks' **Network Co-Pilot Sync (NCPS)** framework. The purpose of this mock agent is to simulate SONiC-based network telemetry and provide a local environment for experimenting with AI integration, data retrieval, and agent-driven network insights.

## Overview

Aviz Networks builds open, modular, and cloud-managed network solutions on top of SONiC (Software for Open Networking in the Cloud). This repository serves as a starting point for understanding how Aviz’s AI agents interact with SONiC data pipelines through the MCP interface.

The mock agent implemented here exposes a minimal server endpoint and a sample AI tool to simulate SONiC telemetry collection and agent communication.

## Features

- **MCP Server (FastMCP)** implementation for agent communication
- **Mock SONiC Telemetry Tool** returning simulated interface data
- Local setup with Python virtual environment and dependency isolation
- Ready for integration with Aviz Network Co-Pilot Sync workflows

## Installation

Clone the repository and set up a Python virtual environment:

```bash
git clone https://github.com/mohsinkhawaja/mock-aviz-agent.git
cd mock-aviz-agent
python -m venv .venv
source .venv/bin/activate
pip install "mcp[cli]"
