"""
Demo LLM Integration for Murphy System
Provides simulated LLM responses without requiring actual API keys.
"""

import logging
import random
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DemoLLMProvider:
    """Demo LLM provider that generates simulated responses."""
    
    def __init__(self):
        """Initialize demo LLM provider."""
        self.available = True
        self.provider_name = "Demo LLM"
        
        # Predefined responses for common queries
        self.responses = {
            "system_overview": """
The Murphy System is a comprehensive business automation platform with:
- 5 AI agents (Executive, Engineering, Financial, Legal, Operations)
- 7 system states showing current workflow progression
- 6 interactive panels for system management
- Real-time monitoring and shadow agent learning
- Artifact generation capabilities

Current Status: All systems operational
Database: Connected with 13 tables
Monitoring: 100% health score
            """.strip(),
            
            "guidance": """
I'm here to help you navigate the Murphy System. Here are some suggestions:

1. Start with /initialize to set up the system
2. Use /status to check system health
3. Try /state list to see available states
4. Explore the 6 interactive panels in the sidebar
5. Use /librarian ask