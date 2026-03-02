"""
Plan Decomposer

Decomposes plans into executable tasks with dependencies, validation criteria,
and human checkpoints.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import sys
import os

# Add murphy_runtime_analysis to path for imports

from .plan_models import (
    Plan,
    Task,
    Dependency,
    ValidationCriterion,
    HumanCheckpoint,
    TaskPriority,
    TaskStatus,
    DependencyType
)

logger = logging.getLogger(__name__)


class PlanDecomposer:
    """
    Decomposes plans into executable tasks
    
    Takes a plan document or goal description and breaks it down into:
    - Individual tasks with clear descriptions
    - Task dependencies and ordering
    - Validation criteria for each task
    - Human checkpoints for review
    - Assumptions and risks
    """
    
    def __init__(self):
        self.task_counter = 0
        self.dependency_counter = 0
        self.criterion_counter = 0
        self.checkpoint_counter = 0
    
    def decompose_uploaded_plan(
        self,
        plan_document_path: str,
        plan_context: str,
        expansion_level: str,
        constraints: List[str],
        validation_criteria: List[str],
        human_checkpoints: List[str]
    ) -> Plan:
        """
        Decompose an uploaded plan document
        
        Args:
            plan_document_path: Path to plan document
            plan_context: Business context
            expansion_level: Detail level (minimal/moderate/comprehensive)
            constraints: Plan constraints
            validation_criteria: Success criteria
            human_checkpoints: When to request human review
            
        Returns:
            Decomposed Plan object
        """
        logger.info(f"Decomposing uploaded plan: {plan_document_path}")
        logger.debug(f"Expansion level: {expansion_level}")
        
        # Extract plan content from document
        plan_content = self._extract_plan_content(plan_document_path)
        
        # Parse plan structure
        plan_structure = self._parse_plan_structure(plan_content, plan_context)
        
        # Generate tasks based on expansion level
        tasks = self._generate_tasks_from_structure(
            plan_structure,
            expansion_level
        )
        
        # Identify dependencies
        dependencies = self._identify_dependencies(tasks)
        
        # Add validation criteria to tasks
        self._add_validation_criteria(tasks, validation_criteria)
        
        # Add human checkpoints
        self._add_human_checkpoints(tasks, human_checkpoints)
        
        # Create plan object
        plan = Plan(
            plan_id=self._generate_plan_id(),
            title=plan_structure.get('title', 'Uploaded Plan'),
            description=plan_structure.get('description', plan_context),
            goal=plan_structure.get('goal', plan_context),
            domain=plan_structure.get('domain', 'custom'),
            timeline=plan_structure.get('timeline', 'TBD'),
            budget=plan_structure.get('budget'),
            tasks=tasks,
            dependencies=dependencies,
            success_criteria=validation_criteria,
            constraints=constraints,
            assumptions=plan_structure.get('assumptions', []),
            risks=plan_structure.get('risks', [])
        )
        
        logger.info(f"Plan decomposed: {len(tasks)} tasks, {len(dependencies)} dependencies")
        
        return plan
    
    def decompose_goal_to_plan(
        self,
        goal: str,
        domain: str,
        timeline: str,
        budget: Optional[float],
        team_size: Optional[int],
        success_criteria: List[str],
        known_constraints: List[str],
        risk_tolerance: str
    ) -> Plan:
        """
        Generate a plan from a goal description
        
        Args:
            goal: What to accomplish
            domain: Domain category
            timeline: When it needs to be done
            budget: Budget in USD
            team_size: Number of people available
            success_criteria: How to measure success
            known_constraints: Known limitations
            risk_tolerance: Risk acceptance level
            
        Returns:
            Generated Plan object
        """
        logger.info(f"Generating plan from goal in domain: {domain}")
        logger.debug(f"Goal: {goal[:100]}...")
        
        # Analyze goal and domain
        goal_analysis = self._analyze_goal(goal, domain)
        
        # Generate task breakdown based on domain best practices
        tasks = self._generate_tasks_from_goal(
            goal_analysis,
            domain,
            timeline,
            budget,
            team_size
        )
        
        # Identify dependencies
        dependencies = self._identify_dependencies(tasks)
        
        # Add validation criteria
        self._add_validation_criteria(tasks, success_criteria)
        
        # Add human checkpoints based on risk tolerance
        checkpoint_config = self._determine_checkpoints_by_risk(risk_tolerance)
        self._add_human_checkpoints(tasks, checkpoint_config)
        
        # Identify assumptions and risks
        assumptions = self._identify_assumptions(goal_analysis, tasks)
        risks = self._identify_risks(goal_analysis, tasks, risk_tolerance)
        
        # Create plan object
        plan = Plan(
            plan_id=self._generate_plan_id(),
            title=goal_analysis.get('title', 'Generated Plan'),
            description=goal_analysis.get('description', goal),
            goal=goal,
            domain=domain,
            timeline=timeline,
            budget=budget,
            tasks=tasks,
            dependencies=dependencies,
            success_criteria=success_criteria,
            constraints=known_constraints,
            assumptions=assumptions,
            risks=risks,
            metadata={
                'team_size': team_size,
                'risk_tolerance': risk_tolerance,
                'generation_method': 'goal_based'
            }
        )
        
        logger.info(f"Plan generated: {len(tasks)} tasks, {len(dependencies)} dependencies")
        
        return plan
    
    def _extract_plan_content(self, plan_document_path: str) -> str:
        """Extract text content from plan document.

        Supports plain-text (``.txt``), Markdown (``.md``), and JSON
        (``.json``) files.  For unsupported formats the raw bytes are
        decoded as UTF-8 with a fallback to Latin-1.
        """
        if not os.path.isfile(plan_document_path):
            logger.warning("Plan document not found: %s", plan_document_path)
            return ""

        try:
            with open(plan_document_path, 'r', encoding='utf-8') as fh:
                content = fh.read()
        except UnicodeDecodeError:
            with open(plan_document_path, 'r', encoding='latin-1') as fh:
                content = fh.read()

        # For JSON documents, extract a readable summary.
        if plan_document_path.endswith('.json'):
            try:
                import json as _json
                data = _json.loads(content)
                if isinstance(data, dict):
                    parts = []
                    for key, val in data.items():
                        parts.append(f"{key}: {val}")
                    content = "\n".join(parts)
            except Exception:
                pass  # keep raw content

        return content.strip()
    
    def _parse_plan_structure(self, plan_content: str, context: str) -> Dict[str, Any]:
        """Parse plan structure from content using lightweight heuristics.

        Scans for Markdown headings (``#``), numbered lists, and common
        section names to build a structured representation.
        """
        lines = plan_content.split('\n') if plan_content else []
        title = context
        sections: List[Dict[str, Any]] = []
        current_section: Optional[Dict[str, Any]] = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Detect Markdown headings.
            if stripped.startswith('#'):
                heading = stripped.lstrip('#').strip()
                if not title or title == context:
                    title = heading
                current_section = {'heading': heading, 'items': []}
                sections.append(current_section)
            elif stripped[0:1].isdigit() or stripped.startswith('-') or stripped.startswith('*'):
                item = stripped.lstrip('0123456789.-*) ').strip()
                if current_section is not None:
                    current_section['items'].append(item)
                else:
                    current_section = {'heading': 'General', 'items': [item]}
                    sections.append(current_section)

        return {
            'title': title or 'Parsed Plan',
            'description': context,
            'goal': context,
            'domain': 'custom',
            'timeline': 'TBD',
            'sections': sections,
        }
    
    def _generate_tasks_from_structure(
        self,
        plan_structure: Dict[str, Any],
        expansion_level: str
    ) -> List[Task]:
        """Generate tasks from plan structure.

        If the parsed plan contains sections with items, each item becomes
        a task.  Otherwise, falls back to generating a number of placeholder
        tasks determined by the *expansion_level*.
        """
        tasks = []

        sections = plan_structure.get('sections', [])
        # When sections have meaningful items, derive tasks from them.
        if sections:
            for section in sections:
                heading = section.get('heading', 'General')
                items = section.get('items', [])
                if not items:
                    # Section with no items becomes a single task.
                    items = [heading]
                for item in items:
                    priority = TaskPriority.HIGH if 'critical' in item.lower() or 'urgent' in item.lower() else TaskPriority.MEDIUM
                    task = Task(
                        task_id=self._generate_task_id(),
                        title=item[:120],
                        description=f"{heading}: {item}",
                        priority=priority,
                        status=TaskStatus.PENDING,
                        estimated_hours=8.0,
                        deliverables=[f"Completed: {item[:80]}"]
                    )
                    tasks.append(task)

        # Fallback: expansion-level based generation.
        if not tasks:
            granularity = {
                'minimal': 5,
                'moderate': 15,
                'comprehensive': 30,
            }
            num_tasks = granularity.get(expansion_level, 15)
            for i in range(num_tasks):
                task = Task(
                    task_id=self._generate_task_id(),
                    title=f"Task {i+1}",
                    description=f"Description for task {i+1}",
                    priority=TaskPriority.MEDIUM,
                    status=TaskStatus.PENDING,
                    estimated_hours=8.0,
                    deliverables=[f"Deliverable for task {i+1}"]
                )
                tasks.append(task)

        return tasks
    
    def _analyze_goal(self, goal: str, domain: str) -> Dict[str, Any]:
        """Analyze goal and extract key information using keyword heuristics.

        Scans the *goal* text for action verbs and domain-relevant nouns
        to build a structured analysis including key objectives, success
        factors, and anticipated challenges.
        """
        goal_lower = goal.lower()

        # Extract objectives from action phrases.
        action_verbs = [
            'build', 'create', 'design', 'develop', 'deploy', 'implement',
            'improve', 'increase', 'launch', 'migrate', 'optimize',
            'reduce', 'automate', 'integrate', 'scale', 'monitor',
        ]
        objectives = [v for v in action_verbs if v in goal_lower]

        # Success factors based on domain.
        domain_factors: Dict[str, List[str]] = {
            'software_development': ['Code quality', 'Test coverage', 'Documentation'],
            'business_strategy': ['Market alignment', 'Revenue growth', 'Stakeholder buy-in'],
            'marketing_campaign': ['Audience reach', 'Conversion rate', 'Brand awareness'],
        }
        factors = domain_factors.get(domain, ['Timely delivery', 'Budget adherence', 'Quality'])

        # Challenges heuristic.
        challenges = []
        if 'migrate' in goal_lower or 'legacy' in goal_lower:
            challenges.append('Legacy system compatibility')
        if 'scale' in goal_lower or 'performance' in goal_lower:
            challenges.append('Performance at scale')
        if not challenges:
            challenges.append('Scope creep')
            challenges.append('Resource constraints')

        return {
            'title': f"{domain.replace('_', ' ').title()} Plan",
            'description': goal,
            'key_objectives': objectives or ['Deliver project successfully'],
            'success_factors': factors,
            'challenges': challenges,
        }
    
    def _generate_tasks_from_goal(
        self,
        goal_analysis: Dict[str, Any],
        domain: str,
        timeline: str,
        budget: Optional[float],
        team_size: Optional[int]
    ) -> List[Task]:
        """Generate tasks from goal analysis"""
        tasks = []
        
        # Domain-specific task templates
        domain_templates = {
            'software_development': [
                'Requirements gathering',
                'System design',
                'Database design',
                'API development',
                'Frontend development',
                'Testing',
                'Deployment',
                'Documentation'
            ],
            'business_strategy': [
                'Market research',
                'Competitive analysis',
                'Strategy formulation',
                'Financial modeling',
                'Implementation planning',
                'Risk assessment',
                'Stakeholder alignment'
            ],
            'marketing_campaign': [
                'Campaign strategy',
                'Target audience research',
                'Content creation',
                'Channel selection',
                'Budget allocation',
                'Campaign execution',
                'Performance tracking',
                'Optimization'
            ]
        }
        
        # Get templates for domain
        templates = domain_templates.get(domain, ['Task 1', 'Task 2', 'Task 3'])
        
        # Generate tasks from templates
        for i, template in enumerate(templates):
            task = Task(
                task_id=self._generate_task_id(),
                title=template,
                description=f"Complete {template.lower()} for the project",
                priority=TaskPriority.MEDIUM if i < len(templates) // 2 else TaskPriority.HIGH,
                status=TaskStatus.PENDING,
                estimated_hours=16.0,
                estimated_cost=budget / len(templates) if budget else None,
                deliverables=[f"{template} deliverable"]
            )
            tasks.append(task)
        
        return tasks
    
    def _identify_dependencies(self, tasks: List[Task]) -> List[Dependency]:
        """Identify dependencies between tasks.

        Uses a two-pass approach:
        1. **Keyword cross-referencing** — if a task's title or description
           references another task's deliverable, a dependency is created.
        2. **Sequential fallback** — for tasks that have no detected
           cross-references, a simple sequential chain is established.
        """
        dependencies = []
        linked_tasks: set = set()

        # Minimum word length for cross-reference matching.
        _MIN_WORD_LEN = 4

        # Pass 1: keyword cross-reference.
        for i, task_a in enumerate(tasks):
            deliverables_lower = [d.lower() for d in task_a.deliverables]
            for j, task_b in enumerate(tasks):
                if j <= i:
                    continue
                desc_lower = task_b.description.lower()
                title_lower = task_b.title.lower()
                for deliv in deliverables_lower:
                    # Check if any significant word from the deliverable
                    # appears in the dependent task.
                    words = [w for w in deliv.split() if len(w) >= _MIN_WORD_LEN]
                    if any(w in desc_lower or w in title_lower for w in words):
                        dep = Dependency(
                            dependency_id=self._generate_dependency_id(),
                            from_task_id=task_a.task_id,
                            to_task_id=task_b.task_id,
                            dependency_type=DependencyType.FINISH_TO_START,
                            lag_days=0,
                        )
                        dependencies.append(dep)
                        task_b.dependencies.append(task_a.task_id)
                        linked_tasks.add(task_a.task_id)
                        linked_tasks.add(task_b.task_id)
                        break  # one link per pair is enough

        # Build a set for O(1) lookup of existing dependency edges.
        existing_edges = {(d.from_task_id, d.to_task_id) for d in dependencies}

        # Pass 2: sequential chain for unlinked tasks.
        for i in range(len(tasks) - 1):
            if tasks[i].task_id not in linked_tasks or tasks[i + 1].task_id not in linked_tasks:
                edge = (tasks[i].task_id, tasks[i + 1].task_id)
                if edge not in existing_edges:
                    dep = Dependency(
                        dependency_id=self._generate_dependency_id(),
                        from_task_id=tasks[i].task_id,
                        to_task_id=tasks[i + 1].task_id,
                        dependency_type=DependencyType.FINISH_TO_START,
                        lag_days=0,
                    )
                    dependencies.append(dep)
                    if tasks[i].task_id not in tasks[i + 1].dependencies:
                        tasks[i + 1].dependencies.append(tasks[i].task_id)

        return dependencies
    
    def _add_validation_criteria(
        self,
        tasks: List[Task],
        validation_criteria: List[str]
    ):
        """Add validation criteria to tasks"""
        # Distribute validation criteria across tasks
        for i, criterion_text in enumerate(validation_criteria):
            task_index = i % len(tasks)
            
            criterion = ValidationCriterion(
                criterion_id=self._generate_criterion_id(),
                description=criterion_text,
                validation_method='human_review',
                is_mandatory=True
            )
            
            tasks[task_index].validation_criteria.append(criterion)
    
    def _add_human_checkpoints(
        self,
        tasks: List[Task],
        checkpoint_config: List[str]
    ):
        """Add human checkpoints to tasks"""
        # Add checkpoints based on configuration
        for task in tasks:
            if 'before_execution' in checkpoint_config:
                checkpoint = HumanCheckpoint(
                    checkpoint_id=self._generate_checkpoint_id(),
                    checkpoint_type='approval',
                    description=f"Approve execution of {task.title}",
                    blocking=True
                )
                task.human_checkpoints.append(checkpoint)
            
            if 'final_review' in checkpoint_config and task == tasks[-1]:
                checkpoint = HumanCheckpoint(
                    checkpoint_id=self._generate_checkpoint_id(),
                    checkpoint_type='validation',
                    description=f"Final review of {task.title}",
                    blocking=True
                )
                task.human_checkpoints.append(checkpoint)
    
    def _determine_checkpoints_by_risk(self, risk_tolerance: str) -> List[str]:
        """Determine checkpoint configuration based on risk tolerance"""
        if risk_tolerance == 'low':
            return ['before_execution', 'after_each_phase', 'final_review']
        elif risk_tolerance == 'medium':
            return ['before_execution', 'final_review']
        else:  # high
            return ['final_review']
    
    def _identify_assumptions(
        self,
        goal_analysis: Dict[str, Any],
        tasks: List[Task]
    ) -> List[str]:
        """Identify plan-level assumptions based on goal analysis and task set.

        Combines generic project assumptions with signals from the goal
        analysis (e.g. if the goal mentions *migration* we assume the
        legacy system will remain available during the transition).
        """
        base_assumptions = [
            'Resources are available as planned',
            'No major external blockers',
            'Team has necessary skills',
        ]

        # Goal-derived assumptions.
        challenges = goal_analysis.get('challenges', [])
        for challenge in challenges:
            ch_lower = challenge.lower()
            if 'legacy' in ch_lower or 'compatibility' in ch_lower:
                base_assumptions.append('Legacy systems remain accessible during migration')
            if 'scale' in ch_lower or 'performance' in ch_lower:
                base_assumptions.append('Infrastructure can be scaled as needed')

        # Task-count assumption.
        if len(tasks) > 20:
            base_assumptions.append('Sufficient bandwidth to manage a large number of parallel tasks')

        return base_assumptions

    def _identify_risks(
        self,
        goal_analysis: Dict[str, Any],
        tasks: List[Task],
        risk_tolerance: str
    ) -> List[str]:
        """Identify plan-level risks using goal analysis and risk tolerance.

        Low risk-tolerance generates more granular risk entries; high
        tolerance keeps only the top-level items.
        """
        base_risks = [
            'Timeline may slip due to unforeseen challenges',
            'Budget may be exceeded',
            'Quality may be compromised under time pressure',
        ]

        challenges = goal_analysis.get('challenges', [])
        for challenge in challenges:
            base_risks.append(f"Challenge identified: {challenge}")

        if risk_tolerance == 'low':
            base_risks.append('Integration failures between dependent tasks')
            base_risks.append('Key personnel unavailability')

        if len(tasks) > 15:
            base_risks.append('Coordination overhead due to large task count')

        return base_risks
    
    def _generate_plan_id(self) -> str:
        """Generate unique plan ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"plan_{timestamp}"
    
    def _generate_task_id(self) -> str:
        """Generate unique task ID"""
        self.task_counter += 1
        return f"task_{self.task_counter:04d}"
    
    def _generate_dependency_id(self) -> str:
        """Generate unique dependency ID"""
        self.dependency_counter += 1
        return f"dep_{self.dependency_counter:04d}"
    
    def _generate_criterion_id(self) -> str:
        """Generate unique criterion ID"""
        self.criterion_counter += 1
        return f"crit_{self.criterion_counter:04d}"
    
    def _generate_checkpoint_id(self) -> str:
        """Generate unique checkpoint ID"""
        self.checkpoint_counter += 1
        return f"chk_{self.checkpoint_counter:04d}"