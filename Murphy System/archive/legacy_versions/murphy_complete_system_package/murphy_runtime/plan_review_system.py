# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Plan Review Interface

Enables users to review, modify, and approve system-generated plans
with intelligent controls (Magnify, Simplify, Edit, Solidify).
"""

import uuid
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import json
import difflib


class PlanState(Enum):
    """States in the plan lifecycle"""
    DRAFT = "draft"              # Initial state
    MAGNIFIED = "magnified"      # Expanded with details
    SIMPLIFIED = "simplified"    # Distilled to essentials
    EDITED = "edited"            # User modified
    SOLIDIFIED = "solidified"    # Ready for execution
    APPROVED = "approved"        # User approved
    REJECTED = "rejected"        # User rejected
    EXECUTING = "executing"      # Currently running
    COMPLETED = "completed"      # Finished
    FAILED = "failed"            # Execution failed


class PlanType(Enum):
    """Types of plans"""
    INITIALIZATION = "initialization"
    DOCUMENT_CREATION = "document_creation"
    ANALYSIS = "analysis"
    TROUBLESHOOTING = "troubleshooting"
    WORKFLOW = "workflow"
    CUSTOM = "custom"


@dataclass
class PlanStep:
    """A single step in a plan"""
    id: str
    command: str
    description: str
    order: int
    estimated_time: Optional[int] = None  # seconds
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, executing, completed, failed
    result: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'command': self.command,
            'description': self.description,
            'order': self.order,
            'estimated_time': self.estimated_time,
            'dependencies': self.dependencies,
            'status': self.status,
            'result': self.result
        }


@dataclass
class PlanVersion:
    """A version of a plan"""
    version: int
    state: PlanState
    content: str
    steps: List[PlanStep]
    modified_by: str  # 'system' or 'user'
    timestamp: datetime
    changes_summary: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'version': self.version,
            'state': self.state.value,
            'content': self.content,
            'steps': [step.to_dict() for step in self.steps],
            'modified_by': self.modified_by,
            'timestamp': self.timestamp.isoformat(),
            'changes_summary': self.changes_summary
        }


@dataclass
class Plan:
    """A complete plan with history"""
    id: str
    name: str
    plan_type: PlanType
    description: str
    current_state: PlanState
    current_version: int
    versions: List[PlanVersion]
    created_at: datetime
    updated_at: datetime
    confidence: float = 0.7
    risk_level: str = "medium"  # low, medium, high
    domains: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'name': self.name,
            'plan_type': self.plan_type.value,
            'description': self.description,
            'current_state': self.current_state.value,
            'current_version': self.current_version,
            'versions': [v.to_dict() for v in self.versions],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'confidence': self.confidence,
            'risk_level': self.risk_level,
            'domains': self.domains,
            'constraints': self.constraints,
            'metadata': self.metadata
        }
    
    def get_current_version(self) -> PlanVersion:
        """Get the current version"""
        return self.versions[self.current_version - 1]
    
    def get_current_content(self) -> str:
        """Get current plan content"""
        return self.get_current_version().content
    
    def get_current_steps(self) -> List[PlanStep]:
        """Get current plan steps"""
        return self.get_current_version().steps


class PlanReviewer:
    """Manages plan review and modification"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.plans: Dict[str, Plan] = {}
    
    def create_plan(
        self,
        name: str,
        plan_type: str,
        description: str,
        initial_content: str,
        initial_steps: List[Dict],
        domains: List[str] = None,
        constraints: List[str] = None
    ) -> Plan:
        """Create a new plan"""
        plan_id = str(uuid.uuid4())
        now = datetime.now()
        
        # Convert steps
        steps = [
            PlanStep(
                id=str(uuid.uuid4()),
                command=step['command'],
                description=step['description'],
                order=i,
                estimated_time=step.get('estimated_time'),
                dependencies=step.get('dependencies', [])
            )
            for i, step in enumerate(initial_steps)
        ]
        
        # Create initial version
        initial_version = PlanVersion(
            version=1,
            state=PlanState.DRAFT,
            content=initial_content,
            steps=steps,
            modified_by='system',
            timestamp=now,
            changes_summary='Initial plan created'
        )
        
        # Create plan
        plan = Plan(
            id=plan_id,
            name=name,
            plan_type=PlanType[plan_type.upper()],
            description=description,
            current_state=PlanState.DRAFT,
            current_version=1,
            versions=[initial_version],
            created_at=now,
            updated_at=now,
            domains=domains or [],
            constraints=constraints or []
        )
        
        self.plans[plan_id] = plan
        return plan
    
    async def magnify(self, plan_id: str, domain: str) -> Dict:
        """Expand plan with domain expertise"""
        plan = self.plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        
        current_content = plan.get_current_content()
        current_steps = plan.get_current_steps()
        
        # Use LLM to expand plan
        if self.llm_client:
            prompt = f"""Expand this plan with {domain} domain expertise.

Current Plan:
{current_content}

Current Steps:
{json.dumps([s.to_dict() for s in current_steps], indent=2)}

Add detailed steps, considerations, and best practices specific to {domain}.
Provide the expanded plan in the same format.

Respond in JSON format:
{{
    "expanded_content": "detailed plan text",
    "expanded_steps": [
        {{"command": "...", "description": "...", "estimated_time": 60}}
    ],
    "changes_summary": "Added {domain} expertise including..."
}}"""
            
            try:
                response = await self.llm_client.generate(prompt, temperature=0.5)
                result = json.loads(response)
                
                # Create new version
                new_steps = [
                    PlanStep(
                        id=str(uuid.uuid4()),
                        command=step['command'],
                        description=step['description'],
                        order=i,
                        estimated_time=step.get('estimated_time'),
                        dependencies=step.get('dependencies', [])
                    )
                    for i, step in enumerate(result['expanded_steps'])
                ]
                
                new_version = PlanVersion(
                    version=plan.current_version + 1,
                    state=PlanState.MAGNIFIED,
                    content=result['expanded_content'],
                    steps=new_steps,
                    modified_by='system',
                    timestamp=datetime.now(),
                    changes_summary=result['changes_summary']
                )
                
                plan.versions.append(new_version)
                plan.current_version += 1
                plan.current_state = PlanState.MAGNIFIED
                plan.updated_at = datetime.now()
                
                if domain not in plan.domains:
                    plan.domains.append(domain)
                
                return {
                    'success': True,
                    'plan': plan.to_dict(),
                    'changes': result['changes_summary']
                }
                
            except Exception as e:
                print(f"LLM magnify error: {e}")
                # Fallback to simple expansion
                return self._simple_magnify(plan, domain)
        else:
            return self._simple_magnify(plan, domain)
    
    def _simple_magnify(self, plan: Plan, domain: str) -> Dict:
        """Simple magnify without LLM"""
        current_content = plan.get_current_content()
        current_steps = plan.get_current_steps()
        
        # Add domain-specific prefix
        expanded_content = f"[{domain.upper()} DOMAIN EXPERTISE]\n\n{current_content}\n\nAdditional {domain} considerations:\n- Domain-specific best practices\n- {domain} compliance requirements\n- {domain} optimization strategies"
        
        # Add a domain-specific step
        new_steps = current_steps.copy()
        new_steps.append(
            PlanStep(
                id=str(uuid.uuid4()),
                command=f"/domain validate {domain}",
                description=f"Validate {domain} domain requirements",
                order=len(new_steps),
                estimated_time=30
            )
        )
        
        new_version = PlanVersion(
            version=plan.current_version + 1,
            state=PlanState.MAGNIFIED,
            content=expanded_content,
            steps=new_steps,
            modified_by='system',
            timestamp=datetime.now(),
            changes_summary=f"Added {domain} domain expertise"
        )
        
        plan.versions.append(new_version)
        plan.current_version += 1
        plan.current_state = PlanState.MAGNIFIED
        plan.updated_at = datetime.now()
        
        if domain not in plan.domains:
            plan.domains.append(domain)
        
        return {
            'success': True,
            'plan': plan.to_dict(),
            'changes': f"Added {domain} domain expertise"
        }
    
    async def simplify(self, plan_id: str) -> Dict:
        """Distill plan to essentials"""
        plan = self.plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        
        current_content = plan.get_current_content()
        current_steps = plan.get_current_steps()
        
        # Use LLM to simplify plan
        if self.llm_client:
            prompt = f"""Simplify this plan to its essential steps only.

Current Plan:
{current_content}

Current Steps ({len(current_steps)} steps):
{json.dumps([s.to_dict() for s in current_steps], indent=2)}

Remove unnecessary details, combine similar steps, focus on core actions.
Keep only the essential steps needed to achieve the goal.

Respond in JSON format:
{{
    "simplified_content": "concise plan text",
    "simplified_steps": [
        {{"command": "...", "description": "...", "estimated_time": 60}}
    ],
    "changes_summary": "Simplified from X to Y steps..."
}}"""
            
            try:
                response = await self.llm_client.generate(prompt, temperature=0.3)
                result = json.loads(response)
                
                # Create new version
                new_steps = [
                    PlanStep(
                        id=str(uuid.uuid4()),
                        command=step['command'],
                        description=step['description'],
                        order=i,
                        estimated_time=step.get('estimated_time'),
                        dependencies=step.get('dependencies', [])
                    )
                    for i, step in enumerate(result['simplified_steps'])
                ]
                
                new_version = PlanVersion(
                    version=plan.current_version + 1,
                    state=PlanState.SIMPLIFIED,
                    content=result['simplified_content'],
                    steps=new_steps,
                    modified_by='system',
                    timestamp=datetime.now(),
                    changes_summary=result['changes_summary']
                )
                
                plan.versions.append(new_version)
                plan.current_version += 1
                plan.current_state = PlanState.SIMPLIFIED
                plan.updated_at = datetime.now()
                
                return {
                    'success': True,
                    'plan': plan.to_dict(),
                    'changes': result['changes_summary']
                }
                
            except Exception as e:
                print(f"LLM simplify error: {e}")
                return self._simple_simplify(plan)
        else:
            return self._simple_simplify(plan)
    
    def _simple_simplify(self, plan: Plan) -> Dict:
        """Simple simplify without LLM"""
        current_content = plan.get_current_content()
        current_steps = plan.get_current_steps()
        
        # Keep only essential steps (remove validation and optional steps)
        essential_steps = [
            step for step in current_steps
            if 'validate' not in step.command.lower() and 'optional' not in step.description.lower()
        ]
        
        # If we removed too many, keep at least half
        if len(essential_steps) < len(current_steps) / 2:
            essential_steps = current_steps[:max(3, len(current_steps) // 2)]
        
        # Simplify content
        simplified_content = current_content.split('\n\n')[0]  # Keep first paragraph
        simplified_content += "\n\nEssential steps only."
        
        new_version = PlanVersion(
            version=plan.current_version + 1,
            state=PlanState.SIMPLIFIED,
            content=simplified_content,
            steps=essential_steps,
            modified_by='system',
            timestamp=datetime.now(),
            changes_summary=f"Simplified from {len(current_steps)} to {len(essential_steps)} steps"
        )
        
        plan.versions.append(new_version)
        plan.current_version += 1
        plan.current_state = PlanState.SIMPLIFIED
        plan.updated_at = datetime.now()
        
        return {
            'success': True,
            'plan': plan.to_dict(),
            'changes': f"Simplified from {len(current_steps)} to {len(essential_steps)} steps"
        }
    
    def edit(self, plan_id: str, changes: Dict) -> Dict:
        """Apply user edits to plan"""
        plan = self.plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        
        current_version = plan.get_current_version()
        
        # Apply changes
        new_content = changes.get('content', current_version.content)
        new_steps = current_version.steps.copy()
        
        # Handle step modifications
        if 'steps' in changes:
            new_steps = [
                PlanStep(
                    id=step.get('id', str(uuid.uuid4())),
                    command=step['command'],
                    description=step['description'],
                    order=i,
                    estimated_time=step.get('estimated_time'),
                    dependencies=step.get('dependencies', [])
                )
                for i, step in enumerate(changes['steps'])
            ]
        
        # Create new version
        new_version = PlanVersion(
            version=plan.current_version + 1,
            state=PlanState.EDITED,
            content=new_content,
            steps=new_steps,
            modified_by='user',
            timestamp=datetime.now(),
            changes_summary=changes.get('summary', 'User modifications applied')
        )
        
        plan.versions.append(new_version)
        plan.current_version += 1
        plan.current_state = PlanState.EDITED
        plan.updated_at = datetime.now()
        
        return {
            'success': True,
            'plan': plan.to_dict(),
            'changes': new_version.changes_summary
        }
    
    def solidify(self, plan_id: str) -> Dict:
        """Lock plan for execution"""
        plan = self.plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        
        current_version = plan.get_current_version()
        
        # Create solidified version (same content, different state)
        new_version = PlanVersion(
            version=plan.current_version + 1,
            state=PlanState.SOLIDIFIED,
            content=current_version.content,
            steps=current_version.steps,
            modified_by='system',
            timestamp=datetime.now(),
            changes_summary='Plan solidified and ready for execution'
        )
        
        plan.versions.append(new_version)
        plan.current_version += 1
        plan.current_state = PlanState.SOLIDIFIED
        plan.updated_at = datetime.now()
        
        return {
            'success': True,
            'plan': plan.to_dict(),
            'message': 'Plan is now locked and ready for execution'
        }
    
    def approve(self, plan_id: str, user_id: str = 'user') -> Dict:
        """Approve plan for execution"""
        plan = self.plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        
        if plan.current_state != PlanState.SOLIDIFIED:
            return {
                'success': False,
                'error': 'Plan must be solidified before approval'
            }
        
        plan.current_state = PlanState.APPROVED
        plan.updated_at = datetime.now()
        plan.metadata['approved_by'] = user_id
        plan.metadata['approved_at'] = datetime.now().isoformat()
        
        return {
            'success': True,
            'plan': plan.to_dict(),
            'message': 'Plan approved and ready for execution'
        }
    
    def reject(self, plan_id: str, reason: str, user_id: str = 'user') -> Dict:
        """Reject plan"""
        plan = self.plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        
        plan.current_state = PlanState.REJECTED
        plan.updated_at = datetime.now()
        plan.metadata['rejected_by'] = user_id
        plan.metadata['rejected_at'] = datetime.now().isoformat()
        plan.metadata['rejection_reason'] = reason
        
        return {
            'success': True,
            'plan': plan.to_dict(),
            'message': f'Plan rejected: {reason}'
        }
    
    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get a plan by ID"""
        return self.plans.get(plan_id)
    
    def list_plans(self, filters: Dict = None) -> List[Plan]:
        """List all plans with optional filters"""
        plans = list(self.plans.values())
        
        if filters:
            if 'state' in filters:
                plans = [p for p in plans if p.current_state.value == filters['state']]
            if 'plan_type' in filters:
                plans = [p for p in plans if p.plan_type.value == filters['plan_type']]
            if 'domain' in filters:
                plans = [p for p in plans if filters['domain'] in p.domains]
        
        return plans
    
    def get_diff(self, plan_id: str, version1: int, version2: int) -> Dict:
        """Get diff between two versions"""
        plan = self.plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        
        if version1 < 1 or version1 > len(plan.versions):
            raise ValueError(f"Invalid version1: {version1}")
        if version2 < 1 or version2 > len(plan.versions):
            raise ValueError(f"Invalid version2: {version2}")
        
        v1 = plan.versions[version1 - 1]
        v2 = plan.versions[version2 - 1]
        
        # Generate diff
        content_diff = list(difflib.unified_diff(
            v1.content.splitlines(),
            v2.content.splitlines(),
            lineterm='',
            fromfile=f'Version {version1}',
            tofile=f'Version {version2}'
        ))
        
        steps_diff = {
            'added': [s.to_dict() for s in v2.steps if s.id not in [s1.id for s1 in v1.steps]],
            'removed': [s.to_dict() for s in v1.steps if s.id not in [s2.id for s2 in v2.steps]],
            'modified': []
        }
        
        return {
            'version1': version1,
            'version2': version2,
            'content_diff': content_diff,
            'steps_diff': steps_diff,
            'summary': f"Changed from {v1.state.value} to {v2.state.value}"
        }


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_plan_review():
        """Test the plan review system"""
        reviewer = PlanReviewer()
        
        # Create a plan
        plan = reviewer.create_plan(
            name="Business Proposal Creation",
            plan_type="document_creation",
            description="Create a comprehensive business proposal",
            initial_content="Create a business proposal with market analysis and financial projections.",
            initial_steps=[
                {"command": "/document create proposal", "description": "Create initial proposal document", "estimated_time": 60},
                {"command": "/domain add business", "description": "Add business domain", "estimated_time": 30},
                {"command": "/document magnify business", "description": "Expand with business expertise", "estimated_time": 120},
            ],
            domains=["business"]
        )
        
        print(f"Created plan: {plan.id}")
        print(f"Initial state: {plan.current_state.value}")
        print(f"Steps: {len(plan.get_current_steps())}")
        print()
        
        # Magnify
        result = await reviewer.magnify(plan.id, "financial")
        print(f"Magnified: {result['changes']}")
        print(f"New state: {plan.current_state.value}")
        print(f"Steps: {len(plan.get_current_steps())}")
        print()
        
        # Simplify
        result = await reviewer.simplify(plan.id)
        print(f"Simplified: {result['changes']}")
        print(f"New state: {plan.current_state.value}")
        print(f"Steps: {len(plan.get_current_steps())}")
        print()
        
        # Solidify
        result = reviewer.solidify(plan.id)
        print(f"Solidified: {result['message']}")
        print(f"New state: {plan.current_state.value}")
        print()
        
        # Approve
        result = reviewer.approve(plan.id)
        print(f"Approved: {result['message']}")
        print(f"Final state: {plan.current_state.value}")
        print()
        
        # Get diff
        diff = reviewer.get_diff(plan.id, 1, plan.current_version)
        print(f"Diff summary: {diff['summary']}")
        print(f"Content changes: {len(diff['content_diff'])} lines")
    
    asyncio.run(test_plan_review())