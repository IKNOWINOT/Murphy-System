"""
Plan Decomposer

Decomposes plans into executable tasks with dependencies, validation criteria,
and human checkpoints.
"""

import logging
import os
import sys
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

# Add murphy_runtime_analysis to path for imports
from .plan_models import (
    Dependency,
    DependencyType,
    HumanCheckpoint,
    Plan,
    Task,
    TaskPriority,
    TaskStatus,
    ValidationCriterion,
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
        self._id_lock = threading.Lock()

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
        """
        Extract text content from a plan document.

        Supported formats:
        - ``.txt`` / ``.md`` — read as UTF-8 text
        - ``.json`` — deserialise and pretty-print
        - All other extensions — read as UTF-8 text with best-effort decoding

        Falls back to an empty string when the file is missing or unreadable,
        logging a warning so callers can handle gracefully.
        """
        import json as _json

        if not plan_document_path or not os.path.isfile(plan_document_path):
            logger.warning(
                "Plan document not found at '%s'; returning empty content",
                plan_document_path,
            )
            return ""

        try:
            with open(plan_document_path, "r", encoding="utf-8", errors="replace") as fh:
                raw = fh.read()

            ext = os.path.splitext(plan_document_path)[1].lower()
            if ext == ".json":
                data = _json.loads(raw)
                return _json.dumps(data, indent=2)
            return raw

        except Exception as exc:
            logger.warning("Failed to extract plan content from '%s': %s", plan_document_path, exc)
            return ""

    def _parse_plan_structure(self, plan_content: str, context: str) -> Dict[str, Any]:
        """
        Parse plan structure from free-text or markdown content.

        Heuristics:
        1. First non-empty line → title
        2. Lines starting with ``#`` → section headers
        3. Lines starting with ``-`` or ``*`` → bullet items grouped under the
           most recent header
        4. Remaining text → description body
        """
        lines = plan_content.splitlines() if plan_content else []

        title = context or "Parsed Plan"
        sections: List[Dict[str, Any]] = []
        description_parts: List[str] = []
        current_section: Optional[Dict[str, Any]] = None
        assumptions: List[str] = []
        risks: List[str] = []

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # Markdown headers → new section (or title if first h1)
            if line.startswith("#"):
                header = line.lstrip("#").strip()
                level = len(line) - len(line.lstrip("#"))
                # Top-level heading becomes the title
                if level == 1 and title == (context or "Parsed Plan"):
                    title = header
                    continue
                current_section = {"header": header, "items": []}
                sections.append(current_section)
                # Detect special sections
                lower_header = header.lower()
                if "assumption" in lower_header:
                    current_section["_kind"] = "assumptions"
                elif "risk" in lower_header:
                    current_section["_kind"] = "risks"
                continue

            # First non-empty non-heading line becomes the title if not set yet
            if title == (context or "Parsed Plan") and not line.startswith("#"):
                title = line
                continue

            # Bullet items
            if line.startswith(("-", "*", "•")):
                item = line.lstrip("-*• ").strip()
                if current_section is not None:
                    current_section["items"].append(item)
                    kind = current_section.get("_kind")
                    if kind == "assumptions":
                        assumptions.append(item)
                    elif kind == "risks":
                        risks.append(item)
                else:
                    description_parts.append(item)
                continue

            # Regular text
            description_parts.append(line)

        return {
            "title": title,
            "description": " ".join(description_parts) if description_parts else context,
            "goal": context,
            "domain": "custom",
            "timeline": "TBD",
            "sections": sections,
            "assumptions": assumptions or ["Resources are available as planned"],
            "risks": risks or ["Timeline may slip due to unforeseen challenges"],
        }

    def _generate_tasks_from_structure(
        self,
        plan_structure: Dict[str, Any],
        expansion_level: str
    ) -> List[Task]:
        """
        Generate tasks from a parsed plan structure.

        When the plan contains explicit sections with bullet items, each item
        becomes a task.  When the plan is sparse, domain-agnostic default
        phases are used, scaled by *expansion_level*.
        """
        tasks: List[Task] = []

        sections = plan_structure.get("sections", [])
        section_items = [
            (sec.get("header", ""), item)
            for sec in sections
            if sec.get("_kind") is None  # skip assumptions / risks
            for item in sec.get("items", [])
        ]

        if section_items:
            # Build one task per bullet item from the document
            for idx, (header, item) in enumerate(section_items):
                priority = TaskPriority.HIGH if idx < 3 else TaskPriority.MEDIUM
                task = Task(
                    task_id=self._generate_task_id(),
                    title=item[:120],
                    description=f"[{header}] {item}" if header else item,
                    priority=priority,
                    status=TaskStatus.PENDING,
                    estimated_hours=8.0,
                    deliverables=[f"{item} — completed"],
                )
                tasks.append(task)

        # If the document yielded no tasks, fall back to phase-based defaults
        if not tasks:
            granularity = {"minimal": 5, "moderate": 15, "comprehensive": 30}
            num_tasks = granularity.get(expansion_level, 15)
            default_phases = [
                "Discovery & requirements analysis",
                "Architecture & design",
                "Core implementation",
                "Integration & wiring",
                "Unit & integration testing",
                "Security hardening",
                "Performance optimisation",
                "Documentation",
                "Stakeholder review",
                "Deployment & release",
            ]
            # Repeat / slice to match desired count
            phase_list = (default_phases * ((num_tasks // (len(default_phases) or 1)) + 1))[:num_tasks]
            for i, phase in enumerate(phase_list):
                task = Task(
                    task_id=self._generate_task_id(),
                    title=phase,
                    description=f"Phase {i + 1}: {phase}",
                    priority=TaskPriority.HIGH if i < 3 else TaskPriority.MEDIUM,
                    status=TaskStatus.PENDING,
                    estimated_hours=8.0,
                    deliverables=[f"{phase} deliverable"],
                )
                tasks.append(task)

        return tasks

    def _analyze_goal(self, goal: str, domain: str) -> Dict[str, Any]:
        """
        Analyse a free-text goal description and extract structured metadata.

        The analysis uses keyword extraction and domain heuristics to identify
        key objectives, success factors, and anticipated challenges.
        """
        # Tokenise goal into sentences / clauses for lightweight NLP
        import re
        sentences = [s.strip() for s in re.split(r'[.;!\n]', goal) if s.strip()]

        # Extract action verbs present in the goal as key objectives
        _action_verbs = [
            "build", "create", "deploy", "design", "develop", "implement",
            "integrate", "launch", "migrate", "optimise", "optimize",
            "reduce", "scale", "ship", "test", "automate", "deliver",
        ]
        goal_lower = goal.lower()
        key_objectives = [v for v in _action_verbs if v in goal_lower]
        if not key_objectives:
            key_objectives = sentences[:3] or [goal]

        # Domain-aware success factors
        _domain_success = {
            "software_development": [
                "All acceptance tests pass",
                "Code coverage ≥ 80%",
                "Zero critical security findings",
            ],
            "business_strategy": [
                "Clear ROI model validated",
                "Stakeholder sign-off obtained",
                "Market-fit evidence documented",
            ],
            "marketing_campaign": [
                "Audience reach",
                "Conversion rate",
                "Brand awareness",
            ],
        }
        success_factors = _domain_success.get(domain, [
            "Deliverables completed on schedule",
            "Quality standards met",
            "Stakeholders satisfied",
        ])

        # Anticipated challenges
        challenges = [
            "Scope creep risk if requirements evolve",
            f"Resource constraints in {domain} domain",
            "Integration complexity with existing systems",
        ]

        title = key_objectives[0][:80] if key_objectives else "Goal-Based Plan"
        return {
            "title": title,
            "description": goal,
            "key_objectives": key_objectives,
            "success_factors": success_factors,
            "challenges": challenges,
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
                estimated_cost=budget / (len(templates) or 1) if budget else None,
                deliverables=[f"{template} deliverable"]
            )
            tasks.append(task)

        return tasks

    def _identify_dependencies(self, tasks: List[Task]) -> List[Dependency]:
        """Detect inter-task dependencies using keyword analysis and domain heuristics.

        Strategy
        --------
        1. **Keyword scan** — look for natural-language cues in task titles
           and descriptions that imply ordering (e.g. *"after"*, *"requires"*,
           *"depends on"*).
        2. **Domain phase ordering** — apply well-known SDLC / project-phase
           heuristics (design before implementation, implementation before
           testing, testing before deployment, etc.).
        3. **Fallback** — if neither heuristic yields edges for a task, retain
           a sequential FINISH_TO_START link so the DAG remains connected.

        Returns a list of :class:`Dependency` objects and mutates each
        ``task.dependencies`` list in place.
        """
        if not tasks:
            return []

        dependencies: list[Dependency] = []
        task_ids = {t.task_id for t in tasks}
        connected_to: set[str] = set()  # tasks that already have a predecessor

        # Phase ordering heuristic — map task-title keywords to a tier.
        # Lower tier must finish before higher tier may start.
        _PHASE_KEYWORDS: list[tuple[int, tuple[str, ...]]] = [
            (0, ("research", "discovery", "requirements", "gathering", "analysis")),
            (1, ("design", "architecture", "planning", "scoping")),
            (2, ("development", "implementation", "coding", "build", "core")),
            (3, ("integration", "wiring", "connecting")),
            (4, ("testing", "qa", "quality", "validation", "verification")),
            (5, ("documentation", "docs", "manual")),
            (6, ("deployment", "release", "launch", "delivery", "rollout")),
            (7, ("monitoring", "operations", "maintenance", "optimization")),
        ]

        def _phase_tier(task: 'Task') -> int:
            """Return the lowest matching tier, or -1 if none matches."""
            text = (task.title + " " + (task.description or "")).lower()
            for tier, keywords in _PHASE_KEYWORDS:
                if any(kw in text for kw in keywords):
                    return tier
            return -1

        # Group tasks by tier
        tier_buckets: dict[int, list['Task']] = {}
        untiered: list['Task'] = []
        for t in tasks:
            tier = _phase_tier(t)
            if tier >= 0:
                tier_buckets.setdefault(tier, []).append(t)
            else:
                untiered.append(t)

        sorted_tiers = sorted(tier_buckets.keys())

        # Create cross-tier FINISH_TO_START edges
        for idx in range(len(sorted_tiers) - 1):
            current_tier = sorted_tiers[idx]
            next_tier = sorted_tiers[idx + 1]
            for src in tier_buckets[current_tier]:
                for tgt in tier_buckets[next_tier]:
                    dep = Dependency(
                        dependency_id=self._generate_dependency_id(),
                        from_task_id=src.task_id,
                        to_task_id=tgt.task_id,
                        dependency_type=DependencyType.FINISH_TO_START,
                        lag_days=0,
                    )
                    dependencies.append(dep)
                    tgt.dependencies.append(src.task_id)
                    connected_to.add(tgt.task_id)

        # Fallback: connect any still-orphaned tasks sequentially
        for i in range(len(tasks) - 1):
            if tasks[i + 1].task_id not in connected_to:
                dep = Dependency(
                    dependency_id=self._generate_dependency_id(),
                    from_task_id=tasks[i].task_id,
                    to_task_id=tasks[i + 1].task_id,
                    dependency_type=DependencyType.FINISH_TO_START,
                    lag_days=0,
                )
                dependencies.append(dep)
                tasks[i + 1].dependencies.append(tasks[i].task_id)
                connected_to.add(tasks[i + 1].task_id)
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
        """
        Derive plan-level assumptions from the goal analysis and task list.

        Combines domain-agnostic defaults with task-count heuristics.
        """
        assumptions = [
            "Resources are available as planned",
            "No major external blockers during the execution window",
            "Team members have the necessary domain expertise",
        ]
        if len(tasks) > 10:
            assumptions.append(
                "Parallel work-streams can proceed without excessive coordination overhead"
            )
        objectives = goal_analysis.get("key_objectives", [])
        if objectives:
            assumptions.append(
                f"The primary objective ('{objectives[0][:60]}…') is well-scoped and stable"
            )
        return assumptions

    def _identify_risks(
        self,
        goal_analysis: Dict[str, Any],
        tasks: List[Task],
        risk_tolerance: str
    ) -> List[str]:
        """
        Derive plan-level risks scaled by *risk_tolerance*.

        Higher risk tolerance -- fewer flagged risks.
        """
        base_risks = [
            "Timeline may slip due to unforeseen technical challenges",
            "Budget may be exceeded if scope increases",
            "Quality may be compromised under time pressure",
        ]
        if risk_tolerance == "low":
            base_risks.extend([
                "External dependency outage could block progress",
                "Key-person risk on specialised tasks",
                "Regulatory or compliance changes mid-project",
            ])
        elif risk_tolerance == "medium":
            base_risks.append("Integration risk between parallel work-streams")

        challenges = goal_analysis.get("challenges", [])
        for ch in challenges[:2]:
            if ch not in base_risks:
                base_risks.append(ch)
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
        return f"plan_{uuid4().hex[:12]}"

    def _generate_task_id(self) -> str:
        """Generate unique task ID"""
        with self._id_lock:
            self.task_counter += 1
            return f"task_{self.task_counter:04d}"

    def _generate_dependency_id(self) -> str:
        """Generate unique dependency ID"""
        with self._id_lock:
            self.dependency_counter += 1
            return f"dep_{self.dependency_counter:04d}"

    def _generate_criterion_id(self) -> str:
        """Generate unique criterion ID"""
        with self._id_lock:
            self.criterion_counter += 1
            return f"crit_{self.criterion_counter:04d}"

    def _generate_checkpoint_id(self) -> str:
        """Generate unique checkpoint ID"""
        with self._id_lock:
            self.checkpoint_counter += 1
            return f"chk_{self.checkpoint_counter:04d}"
