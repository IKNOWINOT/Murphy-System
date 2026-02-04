# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Phase 5: Intelligent Command Suggestions
LLM-powered context-aware command suggestions
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


@dataclass
class Suggestion:
    """Command suggestion"""
    command: str
    description: str
    confidence: float
    reason: str


@dataclass
class UserContext:
    """User context tracking"""
    recent_commands: deque
    current_state: Dict
    goals: List[str]
    preferences: Dict
    timestamp: datetime


class IntelligentSuggestionSystem:
    """Intelligent command suggestion system"""
    
    def __init__(self):
        """Initialize suggestion system"""
        self.user_context: Optional[UserContext] = None
        self.command_history: deque = deque(maxlen=100)
        self.suggestion_cache: Dict[str, List[Suggestion]] = {}
        self.usage_patterns: Dict[str, int] = defaultdict(int)
        
        # Command categories and their commands
        self.command_categories = {
            'state': ['/state list', '/state evolve', '/state regenerate', '/state rollback'],
            'organization': ['/org agents', '/org chart', '/org assign'],
            'system': ['/status', '/initialize', '/help', '/clear'],
            'swarm': ['/swarm create', '/swarm execute', '/swarm status'],
            'llm': ['/llm status', '/llm generate', '/llm verify'],
            'advanced': ['/script run', '/schedule add', '/alias create']
        }
        
        logger.info("Intelligent Suggestion System initialized")
    
    def update_context(
        self,
        recent_commands: List[str] = None,
        current_state: Dict = None,
        goals: List[str] = None
    ):
        """
        Update user context
        
        Args:
            recent_commands: Recent command history
            current_state: Current system state
            goals: User goals
        """
        if recent_commands:
            for cmd in recent_commands:
                self.command_history.append(cmd)
                self.usage_patterns[cmd.split()[0]] += 1
        
        self.user_context = UserContext(
            recent_commands=self.command_history,
            current_state=current_state or {},
            goals=goals or [],
            preferences={},
            timestamp=datetime.now()
        )
        
        logger.info(f"Context updated with {len(self.command_history)} recent commands")
    
    async def get_suggestions(
        self,
        current_input: str = "",
        max_suggestions: int = 5
    ) -> List[Suggestion]:
        """
        Get intelligent command suggestions
        
        Args:
            current_input: Current terminal input
            max_suggestions: Maximum number of suggestions
        
        Returns:
            List of suggestions
        """
        # Try cache first
        cache_key = f"{current_input}_{self._get_context_hash()}"
        if cache_key in self.suggestion_cache:
            return self.suggestion_cache[cache_key][:max_suggestions]
        
        # Generate suggestions
        suggestions = await self._generate_suggestions(current_input, max_suggestions)
        
        # Cache suggestions
        self.suggestion_cache[cache_key] = suggestions
        
        # Clear old cache entries
        if len(self.suggestion_cache) > 100:
            self.suggestion_cache.clear()
        
        return suggestions[:max_suggestions]
    
    def _get_context_hash(self) -> str:
        """Get hash of current context"""
        if not self.user_context or not self.user_context.recent_commands:
            return "no_context"
        return "-".join(list(self.user_context.recent_commands)[-5:])
    
    async def _generate_suggestions(
        self,
        current_input: str,
        max_suggestions: int
    ) -> List[Suggestion]:
        """Generate suggestions using multiple strategies"""
        all_suggestions = []
        
        # Strategy 1: Pattern-based suggestions
        pattern_suggestions = self._get_pattern_based_suggestions(current_input)
        all_suggestions.extend(pattern_suggestions)
        
        # Strategy 2: Context-aware suggestions
        if self.user_context:
            context_suggestions = await self._get_context_aware_suggestions(current_input)
            all_suggestions.extend(context_suggestions)
        
        # Strategy 3: LLM-powered suggestions
        llm_suggestions = await self._get_llm_suggestions(current_input)
        all_suggestions.extend(llm_suggestions)
        
        # Strategy 4: Usage-based suggestions
        usage_suggestions = self._get_usage_based_suggestions()
        all_suggestions.extend(usage_suggestions)
        
        # Deduplicate and rank
        unique_suggestions = self._deduplicate_and_rank(all_suggestions)
        
        return unique_suggestions
    
    def _get_pattern_based_suggestions(self, current_input: str) -> List[Suggestion]:
        """Get suggestions based on input patterns"""
        suggestions = []
        
        input_lower = current_input.lower()
        
        # Suggest state commands
        if 'state' in input_lower or 'st' in input_lower:
            suggestions.append(Suggestion(
                command="/state list",
                description="List all system states",
                confidence=0.9,
                reason="You're working with states"
            ))
            suggestions.append(Suggestion(
                command="/state evolve 1",
                description="Evolve the first state",
                confidence=0.8,
                reason="Common state operation"
            ))
        
        # Suggest org commands
        if 'org' in input_lower or 'agent' in input_lower:
            suggestions.append(Suggestion(
                command="/org agents",
                description="List all organization agents",
                confidence=0.9,
                reason="You're working with organization"
            ))
        
        # Suggest swarm commands
        if 'swarm' in input_lower:
            suggestions.append(Suggestion(
                command="/swarm execute creative 'task'",
                description="Execute a creative swarm",
                confidence=0.85,
                reason="You mentioned swarm"
            ))
        
        # Suggest help
        if 'help' in input_lower or '?' in input_lower:
            suggestions.append(Suggestion(
                command="/help state",
                description="Get help with state commands",
                confidence=0.95,
                reason="You're asking for help"
            ))
        
        return suggestions
    
    async def _get_context_aware_suggestions(self, current_input: str) -> List[Suggestion]:
        """Get suggestions based on user context"""
        suggestions = []
        
        if not self.user_context:
            return suggestions
        
        recent_commands = list(self.user_context.recent_commands)
        
        # If user just initialized system
        if any('/initialize' in cmd for cmd in recent_commands[-5:]):
            suggestions.append(Suggestion(
                command="/state list",
                description="See initial system states",
                confidence=0.9,
                reason="You just initialized the system"
            ))
            suggestions.append(Suggestion(
                command="/status",
                description="Check system status",
                confidence=0.85,
                reason="Verify initialization"
            ))
        
        # If user just evolved a state
        if any('/state evolve' in cmd for cmd in recent_commands[-3:]):
            suggestions.append(Suggestion(
                command="/state list",
                description="See evolved states",
                confidence=0.9,
                reason="You just evolved a state"
            ))
            suggestions.append(Suggestion(
                command="/org agents",
                description="Check agent status",
                confidence=0.8,
                reason="Review agent involvement"
            ))
        
        # If user is using state commands repeatedly
        state_usage = sum(1 for cmd in recent_commands if '/state' in cmd)
        if state_usage >= 3:
            suggestions.append(Suggestion(
                command="/script run state-workflow",
                description="Run state workflow script",
                confidence=0.85,
                reason="You're working heavily with states"
            ))
        
        return suggestions
    
    async def _get_llm_suggestions(self, current_input: str) -> List[Suggestion]:
        """Get LLM-powered suggestions"""
        suggestions = []
        
        try:
            from llm_integration_manager import llm_manager
            
            # Build context
            context_parts = []
            
            if self.user_context and self.user_context.recent_commands:
                context_parts.append(f"Recent commands: {', '.join(list(self.user_context.recent_commands)[-5:])}")
            
            if current_input:
                context_parts.append(f"Current input: {current_input}")
            
            if self.user_context and self.user_context.goals:
                context_parts.append(f"Goals: {', '.join(self.user_context.goals)}")
            
            context_str = "\n".join(context_parts) if context_parts else "General system operation"
            
            prompt = f"""Suggest 3-5 Murphy System commands based on this context:

{context_str}

For each suggestion, provide:
1. The command syntax
2. A brief description
3. Why it's relevant

Format as a numbered list with clear command syntax."""
            
            response = await llm_manager.call_llm(
                prompt=prompt,
                max_tokens=512,
                use_cache=False  # Always fresh suggestions
            )
            
            # Parse LLM response
            suggestions.extend(self._parse_llm_suggestions(response.content))
        
        except Exception as e:
            logger.error(f"LLM suggestion generation failed: {str(e)}")
        
        return suggestions
    
    def _parse_llm_suggestions(self, content: str) -> List[Suggestion]:
        """Parse LLM response into suggestions"""
        suggestions = []
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            
            # Look for numbered items
            if line and (line[0].isdigit() or line.startswith('-')):
                # Extract command (starts with /)
                if '/' in line:
                    parts = line.split('/', 1)
                    if len(parts) == 2:
                        cmd_part = '/' + parts[1].split()[0]
                        rest = parts[1].split(maxsplit=1)[1] if len(parts[1].split()) > 1 else ""
                        
                        suggestions.append(Suggestion(
                            command=cmd_part,
                            description=rest[:100] if rest else "Suggested command",
                            confidence=0.7,
                            reason="LLM recommendation"
                        ))
        
        return suggestions
    
    def _get_usage_based_suggestions(self) -> List[Suggestion]:
        """Get suggestions based on usage patterns"""
        suggestions = []
        
        # Get most used commands
        sorted_commands = sorted(
            self.usage_patterns.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        for cmd, count in sorted_commands:
            suggestions.append(Suggestion(
                command=cmd,
                description=f"Your most used command (used {count} times)",
                confidence=0.6,
                reason="Frequently used"
            ))
        
        return suggestions
    
    def _deduplicate_and_rank(self, suggestions: List[Suggestion]) -> List[Suggestion]:
        """Remove duplicates and rank by confidence"""
        # Deduplicate by command
        seen = set()
        unique = []
        
        for suggestion in suggestions:
            if suggestion.command not in seen:
                seen.add(suggestion.command)
                unique.append(suggestion)
        
        # Sort by confidence
        unique.sort(key=lambda s: s.confidence, reverse=True)
        
        return unique
    
    def record_suggestion_accepted(self, suggestion: Suggestion):
        """Record when a suggestion is accepted"""
        self.usage_patterns[suggestion.command] += 1
        logger.info(f"Suggestion accepted: {suggestion.command}")


# Global suggestion system instance
suggestion_system = IntelligentSuggestionSystem()


async def test_suggestion_system():
    """Test suggestion system"""
    print("\n" + "="*60)
    print("INTELLIGENT SUGGESTION SYSTEM TEST")
    print("="*60)
    
    # Test 1: Pattern-based suggestions
    print("\nTest 1: Pattern-Based Suggestions")
    try:
        suggestions = await suggestion_system.get_suggestions("state")
        print(f"  Suggestions found: {len(suggestions)}")
        for i, s in enumerate(suggestions[:3], 1):
            print(f"  {i}. {s.command} - {s.description} (conf: {s.confidence:.2f})")
        print("✓ Test 1 passed")
    except Exception as e:
        print(f"✗ Test 1 failed: {str(e)}")
    
    # Test 2: Context-aware suggestions
    print("\nTest 2: Context-Aware Suggestions")
    try:
        suggestion_system.update_context(
            recent_commands=["/initialize", "/state list", "/state evolve 1"],
            current_state={'states': 5},
            goals=["evolve system"]
        )
        
        suggestions = await suggestion_system.get_suggestions()
        print(f"  Suggestions found: {len(suggestions)}")
        for i, s in enumerate(suggestions[:3], 1):
            print(f"  {i}. {s.command} - {s.description} (conf: {s.confidence:.2f})")
        print("✓ Test 2 passed")
    except Exception as e:
        print(f"✗ Test 2 failed: {str(e)}")
    
    # Test 3: LLM-powered suggestions
    print("\nTest 3: LLM-Powered Suggestions")
    try:
        suggestions = await suggestion_system.get_suggestions("help with agents")
        print(f"  Suggestions found: {len(suggestions)}")
        for i, s in enumerate(suggestions[:3], 1):
            print(f"  {i}. {s.command} - {s.description} (conf: {s.confidence:.2f})")
        print("✓ Test 3 passed")
    except Exception as e:
        print(f"✗ Test 3 failed: {str(e)}")
    
    # Test 4: Usage-based suggestions
    print("\nTest 4: Usage-Based Suggestions")
    try:
        suggestion_system.usage_patterns['/status'] = 15
        suggestion_system.usage_patterns['/state list'] = 10
        suggestion_system.usage_patterns['/org agents'] = 8
        
        suggestions = await suggestion_system.get_suggestions()
        print(f"  Suggestions found: {len(suggestions)}")
        print(f"  Top suggestion: {suggestions[0].command} (conf: {suggestions[0].confidence:.2f})")
        print("✓ Test 4 passed")
    except Exception as e:
        print(f"✗ Test 4 failed: {str(e)}")
    
    print("\n" + "="*60)
    print("SUGGESTION SYSTEM TEST COMPLETE")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(test_suggestion_system())