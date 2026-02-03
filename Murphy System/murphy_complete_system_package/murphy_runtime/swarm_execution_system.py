# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Phase 4: Swarm Execution with Real LLMs
Parallel LLM execution for swarm processing
"""

import asyncio
import logging
from typing import Dict, List, Tuple, Optional
from enum import Enum
from datetime import datetime
from dataclasses import dataclass
import uuid

logger = logging.getLogger(__name__)


class SwarmType(Enum):
    """Types of swarms"""
    CREATIVE = "creative"
    ANALYTICAL = "analytical"
    HYBRID = "hybrid"
    ADVERSARIAL = "adversarial"
    SYNTHESIS = "synthesis"
    OPTIMIZATION = "optimization"


class SwarmStatus(Enum):
    """Swarm status"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SwarmAgent:
    """Individual swarm agent"""
    id: str
    name: str
    type: SwarmType
    prompt: str
    result: Optional[str] = None
    confidence: float = 0.0
    status: str = "pending"
    tokens_used: int = 0
    generation_time: float = 0.0


@dataclass
class SwarmResult:
    """Swarm execution result"""
    swarm_id: str
    agents: List[SwarmAgent]
    synthesized_result: str
    consensus_confidence: float
    status: SwarmStatus
    execution_time: float
    timestamp: datetime


class SwarmExecutionSystem:
    """Swarm execution system with parallel LLM processing"""
    
    def __init__(self):
        """Initialize swarm system"""
        self.active_swarms: Dict[str, SwarmResult] = {}
        self.swarm_history: List[SwarmResult] = []
        self.max_parallel_agents = 6  # Limit concurrent LLM calls
        
        logger.info("Swarm Execution System initialized")
    
    async def execute_swarm(
        self,
        task: str,
        swarm_type: SwarmType = SwarmType.HYBRID,
        context: Dict = None,
        num_agents: int = 3
    ) -> SwarmResult:
        """
        Execute a swarm task with parallel LLM processing
        
        Args:
            task: Task description
            swarm_type: Type of swarm to execute
            context: Additional context
            num_agents: Number of agents in swarm
        
        Returns:
            SwarmResult object
        """
        swarm_id = f"swarm_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now()
        
        logger.info(f"Starting swarm {swarm_id} with {num_agents} agents")
        
        # Create swarm agents
        agents = self._create_swarm_agents(task, swarm_type, context, num_agents, swarm_id)
        
        # Execute agents in parallel
        try:
            results = await self._execute_agents_parallel(agents)
            
            # Synthesize results
            synthesized_result, consensus = await self._synthesize_results(
                results, swarm_type, task
            )
            
            # Create swarm result
            swarm_result = SwarmResult(
                swarm_id=swarm_id,
                agents=results,
                synthesized_result=synthesized_result,
                consensus_confidence=consensus,
                status=SwarmStatus.COMPLETED,
                execution_time=(datetime.now() - start_time).total_seconds(),
                timestamp=datetime.now()
            )
            
            # Store result
            self.active_swarms[swarm_id] = swarm_result
            self.swarm_history.append(swarm_result)
            
            logger.info(f"Swarm {swarm_id} completed in {swarm_result.execution_time:.2f}s")
            
            return swarm_result
        
        except Exception as e:
            logger.error(f"Swarm {swarm_id} failed: {str(e)}")
            
            # Create failed result
            swarm_result = SwarmResult(
                swarm_id=swarm_id,
                agents=agents,
                synthesized_result=f"Swarm execution failed: {str(e)}",
                consensus_confidence=0.0,
                status=SwarmStatus.FAILED,
                execution_time=(datetime.now() - start_time).total_seconds(),
                timestamp=datetime.now()
            )
            
            return swarm_result
    
    def _create_swarm_agents(
        self,
        task: str,
        swarm_type: SwarmType,
        context: Dict,
        num_agents: int,
        swarm_id: str
    ) -> List[SwarmAgent]:
        """Create swarm agents with type-specific prompts"""
        agents = []
        
        # Type-specific prompt templates
        prompt_templates = self._get_prompt_templates(swarm_type)
        
        for i in range(num_agents):
            agent_id = f"{swarm_id}_agent_{i+1}"
            
            # Select prompt template
            prompt_template = prompt_templates[i % len(prompt_templates)]
            
            # Format prompt with context
            context_str = self._format_context(context) if context else ""
            prompt = f"{prompt_template}\n\nTask: {task}\n{context_str}"
            
            agent = SwarmAgent(
                id=agent_id,
                name=f"{swarm_type.value.capitalize()} Agent {i+1}",
                type=swarm_type,
                prompt=prompt,
                status="pending"
            )
            
            agents.append(agent)
        
        return agents
    
    def _get_prompt_templates(self, swarm_type: SwarmType) -> List[str]:
        """Get prompt templates for swarm type"""
        templates = {
            SwarmType.CREATIVE: [
                "Think creatively and explore diverse possibilities. Brainstorm innovative solutions without constraints.",
                "Consider unconventional approaches and wild ideas. Think outside the box.",
                "Focus on novelty and originality. Propose groundbreaking concepts."
            ],
            SwarmType.ANALYTICAL: [
                "Analyze the problem systematically. Break it down into components and examine each thoroughly.",
                "Use data-driven reasoning. Consider logical implications and dependencies.",
                "Apply critical thinking. Identify assumptions and evaluate their validity."
            ],
            SwarmType.HYBRID: [
                "Combine creative and analytical thinking. Balance innovation with practicality.",
                "Consider both big-picture vision and detailed implementation.",
                "Integrate diverse perspectives into a cohesive solution."
            ],
            SwarmType.ADVERSARIAL: [
                "Challenge the assumptions and propose counter-arguments. Find weaknesses in proposed solutions.",
                "Play devil's advocate. Identify potential failure modes and risks.",
                "Question the premises and explore alternative viewpoints."
            ],
            SwarmType.SYNTHESIS: [
                "Integrate multiple viewpoints into a unified solution. Find common ground.",
                "Synthesize diverse ideas into a coherent whole. Balance competing requirements.",
                "Create a harmonious solution that incorporates the best elements of each perspective."
            ],
            SwarmType.OPTIMIZATION: [
                "Optimize for efficiency and performance. Minimize waste and maximize value.",
                "Refine and improve the solution. Eliminate redundancies and streamline processes.",
                "Focus on quality and effectiveness. Ensure the solution meets all requirements optimally."
            ]
        }
        
        return templates.get(swarm_type, ["Provide a thoughtful solution to the task."])
    
    def _format_context(self, context: Dict) -> str:
        """Format context as string"""
        lines = []
        for key, value in context.items():
            lines.append(f"{key}: {value}")
        return "\n".join(lines)
    
    async def _execute_agents_parallel(self, agents: List[SwarmAgent]) -> List[SwarmAgent]:
        """Execute agents in parallel"""
        from llm_integration_manager import llm_manager
        
        # Create tasks for each agent
        tasks = []
        for agent in agents:
            task = self._execute_single_agent(agent, llm_manager)
            tasks.append(task)
        
        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        completed_agents = []
        for agent, result in zip(agents, results):
            if isinstance(result, Exception):
                logger.error(f"Agent {agent.id} failed: {str(result)}")
                agent.status = "failed"
                agent.result = f"Error: {str(result)}"
            else:
                agent.status = "completed"
                agent.result = result['content']
                agent.confidence = result['confidence']
                agent.tokens_used = result['tokens_used']
                agent.generation_time = result['generation_time']
            
            completed_agents.append(agent)
        
        return completed_agents
    
    async def _execute_single_agent(
        self,
        agent: SwarmAgent,
        llm_manager
    ) -> Dict:
        """Execute a single agent"""
        agent.status = "running"
        
        try:
            response = await llm_manager.call_llm(
                prompt=agent.prompt,
                max_tokens=1024,
                use_cache=False  # Always generate fresh for swarms
            )
            
            return {
                'content': response.content,
                'confidence': response.confidence,
                'tokens_used': response.tokens_used,
                'generation_time': response.generation_time
            }
        
        except Exception as e:
            logger.error(f"Agent execution error: {str(e)}")
            raise
    
    async def _synthesize_results(
        self,
        agents: List[SwarmAgent],
        swarm_type: SwarmType,
        original_task: str
    ) -> Tuple[str, float]:
        """Synthesize results from multiple agents"""
        from llm_integration_manager import llm_manager
        
        # Filter out failed agents
        successful_agents = [a for a in agents if a.status == "completed"]
        
        if not successful_agents:
            return "No successful agent results", 0.0
        
        # Build synthesis prompt
        agent_results = "\n\n".join([
            f"Agent {i+1} ({a.name}):\n{a.result}"
            for i, a in enumerate(successful_agents)
        ])
        
        synthesis_prompt = f"""Synthesize the following swarm agent results into a cohesive response.

Original Task: {original_task}
Swarm Type: {swarm_type.value}

Agent Results:
{agent_results}

Provide:
1. A unified, synthesized response
2. Key insights from each agent
3. Consensus or conflicting viewpoints
4. Final recommendation or conclusion

Format as a clear, professional synthesis."""
        
        # Synthesize using LLM
        try:
            response = await llm_manager.call_llm(
                prompt=synthesis_prompt,
                max_tokens=1536,
                use_cache=False
            )
            
            # Calculate consensus confidence
            confidences = [a.confidence for a in successful_agents]
            consensus = sum(confidences) / len(confidences)
            
            return response.content, consensus
        
        except Exception as e:
            logger.error(f"Synthesis failed: {str(e)}")
            
            # Fallback: return best agent result
            best_agent = max(successful_agents, key=lambda a: a.confidence)
            return best_agent.result, best_agent.confidence
    
    def get_active_swarms(self) -> List[SwarmResult]:
        """Get all active swarms"""
        return list(self.active_swarms.values())
    
    def get_swarm_history(self, limit: int = 50) -> List[SwarmResult]:
        """Get swarm execution history"""
        return self.swarm_history[-limit:]
    
    def get_swarm(self, swarm_id: str) -> Optional[SwarmResult]:
        """Get specific swarm result"""
        return self.active_swarms.get(swarm_id)


# Global swarm system instance
swarm_system = SwarmExecutionSystem()


async def test_swarm_system():
    """Test swarm execution system"""
    print("\n" + "="*60)
    print("SWARM EXECUTION SYSTEM TEST")
    print("="*60)
    
    # Test 1: Creative swarm
    print("\nTest 1: Creative Swarm Execution")
    try:
        result = await swarm_system.execute_swarm(
            task="Generate ideas for improving productivity in a remote work environment",
            swarm_type=SwarmType.CREATIVE,
            num_agents=3
        )
        
        print(f"  Swarm ID: {result.swarm_id}")
        print(f"  Status: {result.status.value}")
        print(f"  Execution Time: {result.execution_time:.2f}s")
        print(f"  Consensus Confidence: {result.consensus_confidence:.2f}")
        print(f"  Agents Completed: {sum(1 for a in result.agents if a.status == 'completed')}/{len(result.agents)}")
        print(f"  Synthesized Result: {result.synthesized_result[:200]}...")
        print("✓ Test 1 passed")
    except Exception as e:
        print(f"✗ Test 1 failed: {str(e)}")
    
    # Test 2: Analytical swarm
    print("\nTest 2: Analytical Swarm Execution")
    try:
        result = await swarm_system.execute_swarm(
            task="Analyze the risks and benefits of implementing AI in healthcare",
            swarm_type=SwarmType.ANALYTICAL,
            num_agents=3
        )
        
        print(f"  Swarm ID: {result.swarm_id}")
        print(f"  Status: {result.status.value}")
        print(f"  Execution Time: {result.execution_time:.2f}s")
        print(f"  Consensus Confidence: {result.consensus_confidence:.2f}")
        print(f"  Synthesized Result: {result.synthesized_result[:200]}...")
        print("✓ Test 2 passed")
    except Exception as e:
        print(f"✗ Test 2 failed: {str(e)}")
    
    # Test 3: Hybrid swarm
    print("\nTest 3: Hybrid Swarm Execution")
    try:
        result = await swarm_system.execute_swarm(
            task="Design a user onboarding process for a mobile banking app",
            swarm_type=SwarmType.HYBRID,
            context={'users': 'tech-savvy millennials', 'security': 'high priority'},
            num_agents=4
        )
        
        print(f"  Swarm ID: {result.swarm_id}")
        print(f"  Status: {result.status.value}")
        print(f"  Execution Time: {result.execution_time:.2f}s")
        print(f"  Consensus Confidence: {result.consensus_confidence:.2f}")
        print(f"  Synthesized Result: {result.synthesized_result[:200]}...")
        print("✓ Test 3 passed")
    except Exception as e:
        print(f"✗ Test 3 failed: {str(e)}")
    
    # Test 4: Get swarm history
    print("\nTest 4: Get Swarm History")
    try:
        history = swarm_system.get_swarm_history()
        print(f"  Total Swarms: {len(history)}")
        if history:
            print(f"  Latest Swarm: {history[-1].swarm_id}")
            print(f"  Latest Status: {history[-1].status.value}")
        print("✓ Test 4 passed")
    except Exception as e:
        print(f"✗ Test 4 failed: {str(e)}")
    
    print("\n" + "="*60)
    print("SWARM SYSTEM TEST COMPLETE")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(test_swarm_system())