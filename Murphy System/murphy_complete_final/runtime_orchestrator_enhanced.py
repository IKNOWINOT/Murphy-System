"""
Murphy System - Enhanced Runtime Orchestrator with Dynamic Agent Generation

Core runtime capabilities:
- Dynamic agent generation from any request
- Automatic task breakdown and parallelization
- Collective mind coordination
- Capacity and rate limit aware scaling
- Applies to ANY task type (books, software, research, operations, etc.)
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class GeneratedAgent:
    """Dynamically generated agent profile"""
    agent_id: str
    role: str
    specialization: str
    task_description: str
    capabilities: List[str]
    prompt_template: str
    dependencies: List[str]
    output_format: str
    context_requirements: List[str]


@dataclass
class Task:
    """Task definition"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    component: str = ""
    action: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    subtasks: List['Task'] = field(default_factory=list)
    assigned_agent: Optional[str] = None
    estimated_complexity: float = 1.0  # 0.0 to 1.0


class CollectiveMind:
    """
    Collective mind coordinator - sees all agent outputs
    Ensures consistency, context matching, and coordination
    """
    
    def __init__(self, llm_manager):
        self.llm_manager = llm_manager
        self.agent_outputs: Dict[str, List[Dict]] = {}  # agent_id -> [outputs]
        self.global_context: Dict[str, Any] = {}
        self.consistency_rules: List[str] = []
        self.shared_knowledge: Dict[str, Any] = {}
        
    def register_agent(self, agent: GeneratedAgent):
        """Register a new agent"""
        self.agent_outputs[agent.agent_id] = []
        logger.info(f"Agent registered: {agent.agent_id} ({agent.role})")
        
    def register_output(self, agent_id: str, output: Dict):
        """Register an agent's output"""
        if agent_id in self.agent_outputs:
            self.agent_outputs[agent_id].append(output)
            
    def get_all_outputs(self) -> Dict[str, List[Dict]]:
        """Get all agent outputs"""
        return self.agent_outputs.copy()
        
    def analyze_global_context(self, task_description: str) -> Dict:
        """
        Analyze all outputs to extract global context
        Themes, terminology, concept flow, consistency patterns
        """
        all_content = []
        all_concepts = []
        
        for agent_id, outputs in self.agent_outputs.items():
            for output in outputs:
                if 'content' in output:
                    all_content.append(output['content'])
                if 'concepts' in output:
                    all_concepts.extend(output['concepts'])
        
        if not all_content:
            return {'themes': [], 'terminology': {}, 'concepts': list(set(all_concepts))}
        
        analysis_prompt = f"""
        Analyze these agent outputs for global context:
        
        Task: {task_description}
        
        All outputs:
        {json.dumps(self.agent_outputs, indent=2)}
        
        Identify:
        1. Common themes that should be consistent
        2. Terminology that must match across all agents
        3. Concept flow and logical progression
        4. Missing connections or gaps
        5. Inconsistencies in tone or approach
        
        Return JSON with: themes, terminology, flow, gaps, inconsistencies
        """
        
        try:
            response = self.llm_manager.generate(analysis_prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                self.global_context = json.loads(json_match.group())
            else:
                self.global_context = {
                    'themes': [],
                    'terminology': {},
                    'flow': [],
                    'gaps': [],
                    'inconsistencies': []
                }
        except Exception as e:
            logger.error(f"Error analyzing global context: {e}")
            self.global_context = {}
            
        return self.global_context
    
    def get_context_for_agent(self, agent_id: str) -> Dict:
        """Get relevant context for a specific agent"""
        context = {
            'global_themes': self.global_context.get('themes', []),
            'terminology': self.global_context.get('terminology', {}),
            'shared_knowledge': self.shared_knowledge,
            'other_agents': []
        }
        
        # Add summaries from other agents
        for other_id, outputs in self.agent_outputs.items():
            if other_id != agent_id and outputs:
                latest = outputs[-1]
                context['other_agents'].append({
                    'agent_id': other_id,
                    'summary': latest.get('summary', ''),
                    'concepts': latest.get('concepts', [])
                })
        
        return context
    
    def ensure_consistency(self, agent_id: str, content: str) -> Tuple[bool, List[str]]:
        """Check if agent output is consistent with global context"""
        if not self.global_context:
            return True, []
        
        issues = []
        
        # Check terminology
        terminology = self.global_context.get('terminology', {})
        for term, standard in terminology.items():
            if term.lower() in content.lower() and standard.lower() not in content.lower():
                issues.append(f"Use '{standard}' instead of '{term}'")
        
        # Check themes
        themes = self.global_context.get('themes', [])
        for theme in themes:
            if theme.lower() not in content.lower():
                issues.append(f"Missing theme: {theme}")
        
        return len(issues) == 0, issues
    
    def update_shared_knowledge(self, key: str, value: Any):
        """Update shared knowledge accessible to all agents"""
        self.shared_knowledge[key] = value
        logger.info(f"Shared knowledge updated: {key}")


class DynamicAgentGenerator:
    """
    Dynamically generates specialized agents based on task analysis
    """
    
    def __init__(self, llm_manager, capacity_limit: int = 9):
        self.llm_manager = llm_manager
        self.capacity_limit = capacity_limit
        
    def analyze_task(self, task_description: str) -> Dict:
        """
        Analyze task to determine:
        - Optimal number of agents
        - Required specializations
        - Task breakdown strategy
        """
        analysis_prompt = f"""
        Analyze this task for optimal agent allocation:
        
        Task: {task_description}
        
        Capacity limit: {self.capacity_limit} agents
        
        Determine:
        1. How many agents are needed? (1 to {self.capacity_limit})
        2. What specializations are required?
        3. How should the task be broken down?
        4. What are the dependencies between subtasks?
        5. What context sharing is needed?
        
        Return JSON with: num_agents, specializations, breakdown, dependencies, context_requirements
        """
        
        try:
            response = self.llm_manager.generate(analysis_prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"Error analyzing task: {e}")
        
        # Fallback: simple breakdown
        return {
            'num_agents': min(3, self.capacity_limit),
            'specializations': ['research', 'content', 'review'],
            'breakdown': ['Research', 'Generate', 'Review'],
            'dependencies': [[], [0], [1]],
            'context_requirements': ['Findings', 'Content', 'Standards']
        }
    
    def generate_agents(self, task_description: str, analysis: Dict) -> List[GeneratedAgent]:
        """
        Generate specialized agents based on task analysis
        """
        agents = []
        
        for i in range(analysis['num_agents']):
            specialization = analysis['specializations'][i]
            breakdown = analysis['breakdown'][i]
            dependencies = analysis['dependencies'][i] if i < len(analysis['dependencies']) else []
            
            # Generate detailed agent profile
            agent_prompt = f"""
            Create a detailed agent profile for task: {task_description}
            
            Role: {specialization} agent
            Responsibility: {breakdown}
            
            Specify:
            - Exact prompt template for this agent
            - Required capabilities
            - Output format
            - Context requirements
            
            Return JSON with: prompt_template, capabilities, output_format, context_requirements
            """
            
            try:
                response = self.llm_manager.generate(agent_prompt)
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    agent_data = json.loads(json_match.group())
                else:
                    agent_data = {
                        'prompt_template': f'Complete the {specialization} task for: {task_description}',
                        'capabilities': ['analysis', 'generation'],
                        'output_format': 'text',
                        'context_requirements': []
                    }
            except Exception as e:
                logger.error(f"Error generating agent {i}: {e}")
                agent_data = {
                    'prompt_template': f'Complete the {specialization} task for: {task_description}',
                    'capabilities': ['analysis', 'generation'],
                    'output_format': 'text',
                    'context_requirements': []
                }
            
            agent = GeneratedAgent(
                agent_id=f"agent_{i+1}",
                role=f"{specialization.capitalize()} Agent",
                specialization=specialization,
                task_description=breakdown,
                capabilities=agent_data.get('capabilities', []),
                prompt_template=agent_data.get('prompt_template', ''),
                dependencies=[f"agent_{dep+1}" for dep in dependencies],
                output_format=agent_data.get('output_format', 'text'),
                context_requirements=agent_data.get('context_requirements', [])
            )
            agents.append(agent)
            
        return agents


class ParallelExecutor:
    """
    Executes tasks in parallel while respecting dependencies and rate limits
    """
    
    def __init__(self, llm_manager, max_parallel: int = 9):
        self.llm_manager = llm_manager
        self.max_parallel = max_parallel
        self.active_executions: Dict[str, asyncio.Task] = {}
        
    async def execute_agent(self, agent: GeneratedAgent, collective_mind: CollectiveMind, 
                          context: Dict = None) -> Dict:
        """
        Execute a single agent with collective mind coordination
        """
        agent_id = agent.agent_id
        
        # Get context from collective mind
        agent_context = collective_mind.get_context_for_agent(agent_id)
        if context:
            agent_context.update(context)
        
        # Build prompt with context
        prompt = agent.prompt_template
        
        if agent_context:
            context_str = json.dumps(agent_context, indent=2)
            prompt = f"""
            Context from other agents:
            {context_str}
            
            Your task:
            {agent.prompt_template}
            """
        
        try:
            # Generate output
            response = self.llm_manager.generate(prompt)
            
            # Check consistency
            is_consistent, issues = collective_mind.ensure_consistency(agent_id, response)
            
            if not is_consistent and issues:
                # Retry with consistency fixes
                retry_prompt = f"""
                Your previous output had these consistency issues:
                {json.dumps(issues)}
                
                Please revise your output to address these issues:
                {response}
                """
                response = self.llm_manager.generate(retry_prompt)
            
            # Extract key concepts
            concepts = self._extract_concepts(response)
            
            output = {
                'agent_id': agent_id,
                'content': response,
                'concepts': concepts,
                'summary': response[:500] + '...' if len(response) > 500 else response,
                'consistent': is_consistent,
                'timestamp': datetime.now().isoformat()
            }
            
            # Register with collective mind
            collective_mind.register_output(agent_id, output)
            
            logger.info(f"Agent {agent_id} execution complete")
            return output
            
        except Exception as e:
            logger.error(f"Agent {agent_id} execution failed: {e}")
            return {
                'agent_id': agent_id,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _extract_concepts(self, content: str) -> List[str]:
        """Extract key concepts from content"""
        import re
        concepts = []
        
        # Extract headers
        headers = re.findall(r'#+\s+(.+)', content)
        concepts.extend(headers)
        
        # Extract bold terms
        bold = re.findall(r'\*\*(.+?)\*\*', content)
        concepts.extend(bold)
        
        return list(set(concepts))[:10]
    
    async def execute_parallel(self, agents: List[GeneratedAgent], 
                              collective_mind: CollectiveMind) -> Dict[str, Dict]:
        """
        Execute agents in parallel, respecting dependencies
        """
        completed = {}
        pending = {agent.agent_id: agent for agent in agents}
        
        while pending:
            # Find agents with satisfied dependencies
            ready = []
            for agent_id, agent in pending.items():
                deps_satisfied = all(
                    dep in completed for dep in agent.dependencies
                )
                if deps_satisfied:
                    ready.append(agent)
            
            if not ready:
                logger.warning("Circular dependencies detected, forcing execution")
                ready = list(pending.values())[:self.max_parallel]
            
            # Execute in batches (respecting max_parallel)
            batch_size = min(self.max_parallel, len(ready))
            batch = ready[:batch_size]
            
            logger.info(f"Executing batch of {len(batch)} agents")
            
            # Create execution tasks
            execution_tasks = []
            for agent in batch:
                task = asyncio.create_task(
                    self.execute_agent(agent, collective_mind)
                )
                execution_tasks.append((agent.agent_id, task))
            
            # Wait for batch completion
            results = await asyncio.gather(*[task for _, task in execution_tasks])
            
            # Register completed agents
            for (agent_id, _), result in zip(execution_tasks, results):
                completed[agent_id] = result
                if agent_id in pending:
                    del pending[agent_id]
                logger.info(f"Agent {agent_id} complete")
        
        return completed


class RuntimeOrchestrator:
    """
    Enhanced Runtime Orchestrator with dynamic agent generation
    """
    
    def __init__(self, llm_manager, capacity_limit: int = 9, max_parallel: int = 9):
        self.llm_manager = llm_manager
        self.capacity_limit = capacity_limit
        self.max_parallel = max_parallel
        
        # Core components
        self.agent_generator = DynamicAgentGenerator(llm_manager, capacity_limit)
        self.collective_mind = CollectiveMind(llm_manager)
        self.parallel_executor = ParallelExecutor(llm_manager, max_parallel)
        
        # Task management
        self.active_tasks: Dict[str, Dict] = {}
        self.task_history: List[Dict] = []
        
        logger.info("Enhanced Runtime Orchestrator initialized")
    
    async def process_request(self, task_description: str, **kwargs) -> Dict:
        """
        Main entry point - processes any request with dynamic agent generation
        
        This works for ANY task type:
        - Book writing
        - Software development
        - Research projects
        - Marketing campaigns
        - Business operations
        - Data analysis
        - etc.
        """
        task_id = str(uuid.uuid4())
        
        logger.info(f"Processing request: {task_description}")
        logger.info(f"Task ID: {task_id}")
        
        # Initialize task tracking
        self.active_tasks[task_id] = {
            'id': task_id,
            'description': task_description,
            'status': 'analyzing',
            'started_at': datetime.now().isoformat(),
            'agents': [],
            'results': {}
        }
        
        try:
            # Step 1: Analyze task and determine optimal approach
            logger.info("Step 1: Analyzing task...")
            analysis = self.agent_generator.analyze_task(task_description)
            num_agents = analysis['num_agents']
            
            logger.info(f"Analysis complete: {num_agents} agents required")
            self.active_tasks[task_id]['analysis'] = analysis
            
            # Step 2: Generate specialized agents
            logger.info("Step 2: Generating specialized agents...")
            agents = self.agent_generator.generate_agents(task_description, analysis)
            
            for agent in agents:
                self.collective_mind.register_agent(agent)
                logger.info(f"Generated agent: {agent.agent_id} ({agent.role})")
            
            self.active_tasks[task_id]['agents'] = [
                {
                    'id': agent.agent_id,
                    'role': agent.role,
                    'specialization': agent.specialization
                }
                for agent in agents
            ]
            
            # Step 3: Execute agents in parallel with collective mind
            logger.info("Step 3: Executing agents in parallel...")
            self.active_tasks[task_id]['status'] = 'executing'
            
            results = await self.parallel_executor.execute_parallel(
                agents, 
                self.collective_mind
            )
            
            self.active_tasks[task_id]['results'] = results
            
            # Step 4: Analyze global context and ensure consistency
            logger.info("Step 4: Analyzing global context...")
            global_context = self.collective_mind.analyze_global_context(task_description)
            
            self.active_tasks[task_id]['global_context'] = global_context
            
            # Step 5: Synthesize final output
            logger.info("Step 5: Synthesizing final output...")
            final_output = await self._synthesize_output(task_description, results, global_context)
            
            self.active_tasks[task_id]['status'] = 'completed'
            self.active_tasks[task_id]['completed_at'] = datetime.now().isoformat()
            self.active_tasks[task_id]['final_output'] = final_output
            
            # Add to history
            self.task_history.append(self.active_tasks[task_id].copy())
            
            logger.info(f"Task {task_id} completed successfully")
            
            return {
                'task_id': task_id,
                'description': task_description,
                'status': 'completed',
                'num_agents': len(agents),
                'results': results,
                'global_context': global_context,
                'final_output': final_output,
                'duration': self._calculate_duration(self.active_tasks[task_id])
            }
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            self.active_tasks[task_id]['status'] = 'failed'
            self.active_tasks[task_id]['error'] = str(e)
            self.active_tasks[task_id]['completed_at'] = datetime.now().isoformat()
            
            return {
                'task_id': task_id,
                'description': task_description,
                'status': 'failed',
                'error': str(e)
            }
    
    async def _synthesize_output(self, task_description: str, 
                                  results: Dict[str, Dict],
                                  global_context: Dict) -> str:
        """
        Synthesize final output from all agent results
        """
        synthesis_prompt = f"""
        Synthesize a final output from these agent results:
        
        Original Task: {task_description}
        
        Agent Results:
        {json.dumps(results, indent=2)}
        
        Global Context:
        {json.dumps(global_context, indent=2)}
        
        Create a cohesive final output that:
        - Integrates all agent contributions
        - Maintains consistency with global context
        - Addresses the original task completely
        - Is well-structured and professional
        
        Return the complete synthesized output:
        """
        
        try:
            return self.llm_manager.generate(synthesis_prompt)
        except Exception as e:
            logger.error(f"Error synthesizing output: {e}")
            # Fallback: concatenate results
            return "\n\n".join([
                f"### {agent_id} Output\n{result.get('content', result.get('error', 'No content'))}"
                for agent_id, result in results.items()
            ])
    
    def _calculate_duration(self, task: Dict) -> float:
        """Calculate task duration in seconds"""
        if 'started_at' not in task or 'completed_at' not in task:
            return 0.0
        
        start = datetime.fromisoformat(task['started_at'])
        end = datetime.fromisoformat(task['completed_at'])
        return (end - start).total_seconds()
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get status of a specific task"""
        if task_id in self.active_tasks:
            return self.active_tasks[task_id]
        return None
    
    def get_all_tasks(self) -> List[Dict]:
        """Get all task history"""
        return self.task_history.copy()
    
    def set_capacity_limit(self, limit: int):
        """Update capacity limit (for rate limiting)"""
        self.capacity_limit = limit
        self.agent_generator.capacity_limit = limit
        logger.info(f"Capacity limit updated to {limit}")
    
    def set_max_parallel(self, limit: int):
        """Update max parallel executions"""
        self.max_parallel = limit
        self.parallel_executor.max_parallel = limit
        logger.info(f"Max parallel updated to {limit}")


# Singleton instance
_orchestrator_instance: Optional[RuntimeOrchestrator] = None


def get_orchestrator(llm_manager=None) -> RuntimeOrchestrator:
    """Get or create the orchestrator instance"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        if not llm_manager:
            raise ValueError("LLM manager required for first initialization")
        _orchestrator_instance = RuntimeOrchestrator(llm_manager)
    return _orchestrator_instance


def reset_orchestrator():
    """Reset the orchestrator instance"""
    global _orchestrator_instance
    _orchestrator_instance = None