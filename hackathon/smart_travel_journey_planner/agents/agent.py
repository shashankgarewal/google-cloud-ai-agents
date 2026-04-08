"""
agents/agent.py
The single entry point for ADK (adk web / adk run).
Now located inside the agents/ folder.
"""
from __future__ import annotations
import os
import sys

# Ensure the parent directory is in the path so relative imports work if run as a script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Import the Lead Orchestrator using a relative path
from .orchestrator import orchestrator_agent

# ADK looks for 'root_agent' by default
root_agent = orchestrator_agent
