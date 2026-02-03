# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy Swarm System - Knowledge Pipeline Architecture
Integrates with existing swarm to add bucket/pipeline functionality
"""

import asyncio
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid


class ConfidenceLevel(Enum):
    """Confidence levels for blocks"""
    GREEN = "green"    # 95%+ confidence, verified
    YELLOW = "yellow"  # Problematic but functional
    RED = "red"        # Major information needed


class BlockAction(Enum):
    """Actions available for each block"""
    MAGNIFY = "magnify"    # Expand, possibly split into sub-agents
    SIMPLIFY = "simplify"  # Reduce granularity, merge
    SOLIDIFY = "solidify"  # Adapt to our system specifically
    SPLIT = "split"        # Split into multiple agents
    ABSORB = "absorb"      # Merge with another task


@dataclass
class KnowledgeBucket:
    """A bucket that collects filtered information"""
    bucket_id: str
    valve_type: str  # category, customer, area, etc.
    contents: List[Dict] = field(default_factory=list)
    filters: List[str] = field(default_factory=list)
    agents: List[str] = field(default_factory=list)
    confidence: float = 0.0
    
    def fill(self, information: Dict, filter_criteria: List[str]) -> Dict:
        """Fill bucket with filtered information"""
        filtered = self._apply_filters(information, filter_criteria)
        self.contents.append(filtered)
        self._update_confidence()
        return filtered
    
    def _apply_filters(self, info: Dict, criteria: List[str]) -> Dict:
        """Apply filters to information"""
        filtered = {}
        for key, value in info.items():
            if any(criterion in str(value).lower() for criterion in criteria):
                filtered[key] = value
        return filtered
    
    def _update_confidence(self):
        """Update confidence based on contents"""
        if self.contents:
            self.confidence = min(95.0, len(self.contents) * 10)
    
    def flow_to(self, target_bucket: 'KnowledgeBucket') -> List[Dict]:
        """Flow contents to another bucket"""
        return self.contents.copy()


@dataclass
class Block:
    """A task block with confidence and actions"""
    block_id: str
    name: str
    content: str
    confidence: ConfidenceLevel
    dependencies: List[str] = field(default_factory=list)
    affects: List[str] = field(default_factory=list)
    agent_id: Optional[str] = None
    questions: List[str] = field(default_factory=list)
    status: str = "pending"
    
    def get_color(self) -> str:
        """Get color based on confidence"""
        return self.confidence.value
    
    def needs_human_input(self) -> bool:
        """Check if human input needed"""
        return self.confidence in [ConfidenceLevel.YELLOW, ConfidenceLevel.RED]


class GlobalStateManager:
    """Manages global state and cascading updates"""
    
    def __init__(self):
        self.state: Dict[str, Block] = {}
        self.dependencies: Dict[str, List[str]] = {}
        self.cascade_queue: List[str] = []
        self.timeline: List[Dict] = []
        
    def register_block(self, block: Block):
        """Register a block in global state"""
        self.state[block.block_id] = block
        self.dependencies[block.block_id] = block.dependencies
        
    def update_block(self, block_id: str, new_content: str) -> List[str]:
        """Update a block and return affected blocks"""
        if block_id in self.state:
            self.state[block_id].content = new_content
            
            # Find downstream dependencies
            affected = self.find_downstream_dependencies(block_id)
            
            # Add to cascade queue
            self.cascade_queue.extend(affected)
            
            # Update timeline
            self._update_timeline(block_id, affected)
            
            return affected
        return []
    
    def find_downstream_dependencies(self, block_id: str) -> List[str]:
        """Find all blocks that depend on this one"""
        affected = []
        for block, deps in self.dependencies.items():
            if block_id in deps:
                affected.append(block)
                # Recursively find dependencies
                affected.extend(self.find_downstream_dependencies(block))
        return list(set(affected))
    
    def _update_timeline(self, changed_block: str, affected_blocks: List[str]):
        """Update master scheduler timeline"""
        self.timeline.append({
            'timestamp': datetime.now().isoformat(),
            'changed': changed_block,
            'affected': affected_blocks,
            'action': 'cascade_update'
        })
    
    def get_regeneration_order(self, blocks: List[str]) -> List[str]:
        """Get correct order for regenerating blocks"""
        # Topological sort based on dependencies
        ordered = []
        visited = set()
        
        def visit(block_id):
            if block_id in visited:
                return
            visited.add(block_id)
            
            # Visit dependencies first
            if block_id in self.dependencies:
                for dep in self.dependencies[block_id]:
                    if dep in blocks:
                        visit(dep)
            
            ordered.append(block_id)
        
        for block in blocks:
            visit(block)
        
        return ordered


class InformationSourceDecider:
    """Decides where information should come from"""
    
    REAL_WORLD_INDICATORS = [
        'customer_specific', 'proprietary', 'measured_data',
        'legal_documents', 'financial_records', 'brand_guidelines',
        'existing_content', 'sales_data', 'user_preferences'
    ]
    
    def __init__(self, llm_manager):
        self.llm_manager = llm_manager
    
    def decide_source(self, information_needed: str, user_capability: bool = False) -> Dict:
        """Decide if user provides, we generate, or hire external"""
        
        if self._is_real_world_data(information_needed):
            if user_capability:
                return {
                    'source': 'user',
                    'action': 'request_from_user',
                    'questions': self._generate_questions(information_needed)
                }
            else:
                return {
                    'source': 'external',
                    'action': 'hire_collection',
                    'cost': self._estimate_cost(information_needed),
                    'requires': 'change_order_approval'
                }
        else:
            return {
                'source': 'ai_generate',
                'action': 'generate',
                'confidence': 0.85
            }
    
    def _is_real_world_data(self, info: str) -> bool:
        """Check if this requires real-world data"""
        info_lower = info.lower()
        return any(indicator in info_lower for indicator in self.REAL_WORLD_INDICATORS)
    
    def _generate_questions(self, info_needed: str) -> List[str]:
        """Generate questions to gather information from user"""
        prompt = f"Generate 3-5 specific questions to gather this information from the user: {info_needed}"
        response = self.llm_manager.generate(prompt)
        # Parse questions from response
        questions = [q.strip() for q in response.split('\n') if q.strip() and '?' in q]
        return questions[:5]
    
    def _estimate_cost(self, info_needed: str) -> float:
        """Estimate cost of external collection"""
        # Simple estimation based on complexity
        complexity = len(info_needed.split())
        base_cost = 500.0
        return base_cost + (complexity * 10)


class BlockVerification:
    """Handles Magnify/Simplify/Solidify actions"""
    
    def __init__(self, llm_manager, global_state: GlobalStateManager):
        self.llm_manager = llm_manager
        self.global_state = global_state
    
    def magnify(self, block: Block) -> Dict:
        """Expand complexity, possibly split into sub-agents"""
        prompt = f"""
        Analyze this task block for expansion:
        
        Block: {block.name}
        Content: {block.content}
        
        Determine:
        1. Should this be expanded with more detail?
        2. Is it complex enough to split into sub-agents?
        3. What subtasks would be created?
        
        Return JSON with: should_split, subtasks, expanded_content
        """
        
        response = self.llm_manager.generate(prompt)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                if result.get('should_split'):
                    return {
                        'action': 'split',
                        'subtasks': result.get('subtasks', []),
                        'recommendation': 'Split into multiple agents for better confidence'
                    }
                else:
                    return {
                        'action': 'expand',
                        'content': result.get('expanded_content', block.content),
                        'recommendation': 'Expanded with more detail'
                    }
        except:
            pass
        
        return {'action': 'expand', 'content': block.content}
    
    def simplify(self, block: Block) -> Dict:
        """Reduce granularity if too complex"""
        prompt = f"""
        Analyze this task block for simplification:
        
        Block: {block.name}
        Content: {block.content}
        
        Determine:
        1. Is this too granular?
        2. Should subtasks be merged?
        3. What's the simplified version?
        
        Return JSON with: too_granular, merge_with, simplified_content
        """
        
        response = self.llm_manager.generate(prompt)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                return {
                    'action': 'simplify',
                    'content': result.get('simplified_content', block.content),
                    'merge_with': result.get('merge_with', []),
                    'recommendation': 'Reduced complexity for better management'
                }
        except:
            pass
        
        return {'action': 'simplify', 'content': block.content}
    
    def solidify(self, block: Block) -> Dict:
        """Adapt to our system specifically"""
        # Get global state context
        all_blocks = self.global_state.state
        
        prompt = f"""
        Adapt this task block to fit our Murphy system specifically:
        
        Block: {block.name}
        Content: {block.content}
        
        Global Context:
        {json.dumps({k: v.name for k, v in all_blocks.items()}, indent=2)}
        
        Determine:
        1. How should this be adapted for Murphy system?
        2. Are there inconsistencies with other blocks?
        3. Should this absorb another task?
        
        Return JSON with: adapted_content, inconsistencies, absorb_tasks
        """
        
        response = self.llm_manager.generate(prompt)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                action = 'solidify'
                if result.get('absorb_tasks'):
                    action = 'absorb'
                
                return {
                    'action': action,
                    'content': result.get('adapted_content', block.content),
                    'absorb_tasks': result.get('absorb_tasks', []),
                    'inconsistencies': result.get('inconsistencies', []),
                    'recommendation': 'Adapted to Murphy system specifications'
                }
        except:
            pass
        
        return {'action': 'solidify', 'content': block.content}


class OrgChartLibrary:
    """Library of templated org charts for different industries"""
    
    TEMPLATES = {
        'publishing': {
            'roles': ['CEO', 'Research', 'Content', 'Editor', 'Marketing', 'Sales'],
            'strategies': ['content_first', 'market_driven', 'quality_focus'],
            'lucrative_strategies': ['bestseller_analysis', 'niche_targeting', 'series_development']
        },
        'software': {
            'roles': ['CEO', 'Product', 'Engineering', 'QA', 'DevOps', 'Sales'],
            'strategies': ['agile', 'continuous_delivery', 'user_feedback'],
            'lucrative_strategies': ['saas_model', 'enterprise_focus', 'api_first']
        },
        'consulting': {
            'roles': ['CEO', 'Business_Dev', 'Consultants', 'Research', 'Delivery'],
            'strategies': ['expertise_based', 'relationship_driven', 'results_focused'],
            'lucrative_strategies': ['retainer_model', 'value_pricing', 'specialization']
        }
    }
    
    def __init__(self, llm_manager):
        self.llm_manager = llm_manager
    
    def match_org_chart(self, business_description: str, public_strategies: List[str] = None) -> Dict:
        """Match business to org chart template and adapt strategies"""
        
        # Detect industry
        industry = self._detect_industry(business_description)
        
        # Get base template
        template = self.TEMPLATES.get(industry, self.TEMPLATES['consulting'])
        
        # Adapt based on public strategies
        if public_strategies:
            adapted = self._adapt_strategies(template, public_strategies)
        else:
            adapted = template
        
        # Solidify for Murphy system
        solidified = self._solidify_for_murphy(adapted)
        
        return {
            'industry': industry,
            'org_chart': solidified['roles'],
            'strategies': solidified['strategies'],
            'implementation': solidified['murphy_specific']
        }
    
    def _detect_industry(self, description: str) -> str:
        """Detect industry from description"""
        description_lower = description.lower()
        
        if any(word in description_lower for word in ['book', 'publish', 'author', 'content']):
            return 'publishing'
        elif any(word in description_lower for word in ['software', 'app', 'saas', 'tech']):
            return 'software'
        elif any(word in description_lower for word in ['consult', 'advisory', 'service']):
            return 'consulting'
        
        return 'consulting'  # default
    
    def _adapt_strategies(self, template: Dict, public_strategies: List[str]) -> Dict:
        """Adapt template based on public strategies with weighted lucrative ones"""
        adapted = template.copy()
        
        # Weight lucrative strategies higher
        weighted_strategies = []
        for strategy in public_strategies:
            if strategy in template['lucrative_strategies']:
                weighted_strategies.append({'strategy': strategy, 'weight': 2.0})
            else:
                weighted_strategies.append({'strategy': strategy, 'weight': 1.0})
        
        adapted['weighted_strategies'] = weighted_strategies
        return adapted
    
    def _solidify_for_murphy(self, template: Dict) -> Dict:
        """Solidify template for Murphy system specifically"""
        prompt = f"""
        Adapt this org chart template for Murphy system implementation:
        
        Template: {json.dumps(template, indent=2)}
        
        Determine:
        1. How should each role be implemented as Murphy agents?
        2. What Murphy-specific workflows are needed?
        3. What automation opportunities exist?
        
        Return JSON with: roles, strategies, murphy_specific
        """
        
        response = self.llm_manager.generate(prompt)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        return template


class LibrarianCommandGenerator:
    """Generates commands for librarian based on vague requests"""
    
    def __init__(self, llm_manager):
        self.llm_manager = llm_manager
    
    def explode_request(self, vague_request: str) -> Dict:
        """Explode vague request into everything required"""
        
        prompt = f"""
        User request: "{vague_request}"
        
        Generate a complete automation plan with:
        
        1. ORG CHART:
           - Required roles (CEO, Research, Operations, Sales/Marketing, R&D, etc.)
           - Responsibilities per role
           - Communication flows
        
        2. KEY ASPECTS:
           - Executive branch (strategy, oversight)
           - Directors (operations, sales/marketing, R&D)
           - Shadow system (state flow definitions)
           - Business development & community outreach
        
        3. QUANTUM LEVEL ANALYSIS:
           - Known probable errors
           - Contingency plans
           - Risk mitigation strategies
        
        4. INFORMATION REQUIREMENTS:
           - What must come from user (GREEN/YELLOW/RED confidence)
           - What can be generated
           - What needs external collection
        
        5. TASK BLOCKS:
           - Main tasks
           - Subtasks
           - Dependencies
           - Confidence levels
        
        Return comprehensive JSON with all above sections.
        """
        
        response = self.llm_manager.generate(prompt)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                plan = json.loads(json_match.group())
                
                # Librarian should generate 80% automatically
                plan['auto_generated_percentage'] = 80
                plan['requires_human_input'] = self._identify_human_input_needs(plan)
                
                return plan
        except Exception as e:
            # Fallback structure
            return {
                'org_chart': [],
                'key_aspects': {},
                'quantum_analysis': {},
                'information_requirements': {},
                'task_blocks': [],
                'auto_generated_percentage': 0,
                'requires_human_input': []
            }
    
    def _identify_human_input_needs(self, plan: Dict) -> List[Dict]:
        """Identify blocks needing human input with confidence levels"""
        needs = []
        
        for block in plan.get('task_blocks', []):
            confidence = block.get('confidence', 50)
            
            if confidence >= 95:
                color = ConfidenceLevel.GREEN
                action_needed = None
            elif confidence >= 70:
                color = ConfidenceLevel.YELLOW
                action_needed = 'answer_questions_before_generation'
            else:
                color = ConfidenceLevel.RED
                action_needed = 'major_information_needed'
            
            if action_needed:
                needs.append({
                    'block': block.get('name'),
                    'confidence': confidence,
                    'color': color.value,
                    'action_needed': action_needed,
                    'questions': block.get('questions', [])
                })
        
        return needs


class MasterScheduler:
    """Master scheduler for aligning priority and ordering tasks"""
    
    def __init__(self, global_state: GlobalStateManager):
        self.global_state = global_state
        self.priority_queue: List[Tuple[int, str]] = []  # (priority, block_id)
        self.feedback_loops: Dict[str, List[str]] = {}  # agent_id -> [corrections]
    
    def schedule_tasks(self, blocks: List[Block]) -> List[str]:
        """Schedule tasks based on dependencies and priorities"""
        # Build priority queue
        for block in blocks:
            priority = self._calculate_priority(block)
            self.priority_queue.append((priority, block.block_id))
        
        # Sort by priority (lower number = higher priority)
        self.priority_queue.sort()
        
        # Get execution order respecting dependencies
        execution_order = []
        executed = set()
        
        while self.priority_queue:
            priority, block_id = self.priority_queue.pop(0)
            block = self.global_state.state.get(block_id)
            
            if not block:
                continue
            
            # Check if dependencies are met
            deps_met = all(dep in executed for dep in block.dependencies)
            
            if deps_met:
                execution_order.append(block_id)
                executed.add(block_id)
            else:
                # Re-queue with lower priority
                self.priority_queue.append((priority + 1, block_id))
        
        return execution_order
    
    def _calculate_priority(self, block: Block) -> int:
        """Calculate priority based on confidence, dependencies, and impact"""
        base_priority = 10
        
        # Lower priority for low confidence (needs attention first)
        if block.confidence == ConfidenceLevel.RED:
            base_priority -= 5
        elif block.confidence == ConfidenceLevel.YELLOW:
            base_priority -= 2
        
        # Higher priority for blocks with many dependents
        num_dependents = len(block.affects)
        base_priority -= num_dependents
        
        # Lower priority for blocks with many dependencies
        num_dependencies = len(block.dependencies)
        base_priority += num_dependencies
        
        return max(0, base_priority)
    
    def add_feedback_loop(self, agent_id: str, correction: str):
        """Add feedback loop correction for an agent"""
        if agent_id not in self.feedback_loops:
            self.feedback_loops[agent_id] = []
        self.feedback_loops[agent_id].append(correction)
    
    def get_feedback_for_agent(self, agent_id: str) -> List[str]:
        """Get feedback corrections for an agent"""
        return self.feedback_loops.get(agent_id, [])


# Integration function for Murphy system
def initialize_knowledge_pipeline(llm_manager) -> Dict:
    """Initialize the knowledge pipeline system"""
    
    global_state = GlobalStateManager()
    info_decider = InformationSourceDecider(llm_manager)
    block_verification = BlockVerification(llm_manager, global_state)
    org_chart_library = OrgChartLibrary(llm_manager)
    librarian_commands = LibrarianCommandGenerator(llm_manager)
    master_scheduler = MasterScheduler(global_state)
    
    return {
        'global_state': global_state,
        'info_decider': info_decider,
        'block_verification': block_verification,
        'org_chart_library': org_chart_library,
        'librarian_commands': librarian_commands,
        'master_scheduler': master_scheduler
    }