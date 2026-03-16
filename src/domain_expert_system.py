"""
Domain Expert Swarm System
Creates domain expert teams based on organization charts and job positions.
Uses RLM patterns for intelligent task decomposition.
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExpertiseLevel(Enum):
    """Levels of expertise for domain experts."""
    JUNIOR = "junior"
    INTERMEDIATE = "intermediate"
    SENIOR = "senior"
    EXPERT = "expert"


class KnowledgeType(Enum):
    """Types of knowledge domains."""
    TECHNICAL = "technical"
    CREATIVE = "creative"
    BUSINESS = "business"
    MANAGEMENT = "management"
    OPERATIONS = "operations"
    RESEARCH = "research"
    COMMUNICATION = "communication"


@dataclass
class KnowledgeContext:
    """Represents the knowledge context for a domain expert."""
    knowledge_type: KnowledgeType
    topics: List[str]
    skills: List[str]
    tools: List[str]
    questions_to_ask: List[str]
    artifacts_can_create: List[str]

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "knowledge_type": self.knowledge_type.value,
            "topics": self.topics,
            "skills": self.skills,
            "tools": self.tools,
            "questions_to_ask": self.questions_to_ask,
            "artifacts_can_create": self.artifacts_can_create
        }


@dataclass
class DomainExpert:
    """Represents a domain expert role."""
    job_title: str
    expertise_level: ExpertiseLevel
    knowledge_context: KnowledgeContext
    responsibilities: List[str]
    collaboration_with: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "job_title": self.job_title,
            "expertise_level": self.expertise_level.value,
            "knowledge_context": self.knowledge_context.to_dict(),
            "responsibilities": self.responsibilities,
            "collaboration_with": self.collaboration_with
        }


@dataclass
class Artifact:
    """Represents a project artifact."""
    name: str
    type: str
    description: str
    created_by: str
    content: str
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "created_by": self.created_by,
            "content": self.content,
            "dependencies": self.dependencies
        }


class DomainExpertSwarm:
    """
    Manages domain expert swarms for project execution.
    Uses RLM patterns to decompose tasks and assign to experts.
    """

    def __init__(self):
        self.experts: Dict[str, DomainExpert] = {}
        self.artifacts: Dict[str, Artifact] = {}
        self._initialize_expert_database()

    def _initialize_expert_database(self):
        """Initialize common domain expert roles."""

        # Software Development Experts
        self._add_expert(DomainExpert(
            job_title="Software Architect",
            expertise_level=ExpertiseLevel.SENIOR,
            knowledge_context=KnowledgeContext(
                knowledge_type=KnowledgeType.TECHNICAL,
                topics=["system design", "architecture patterns", "scalability", "performance"],
                skills=["system design", "technical decision making", "code review", "mentoring"],
                tools=["architecture diagrams", "API design", "cloud platforms"],
                questions_to_ask=[
                    "What are the main features needed?",
                    "How many users will use this system?",
                    "What are the performance requirements?",
                    "What technologies are preferred?"
                ],
                artifacts_can_create=["architecture diagrams", "API specifications", "technical specs"]
            ),
            responsibilities=["design system architecture", "make technical decisions", "review code"]
        ))

        self._add_expert(DomainExpert(
            job_title="Frontend Developer",
            expertise_level=ExpertiseLevel.INTERMEDIATE,
            knowledge_context=KnowledgeContext(
                knowledge_type=KnowledgeType.TECHNICAL,
                topics=["user interfaces", "web frameworks", "responsive design", "accessibility"],
                skills=["HTML/CSS/JavaScript", "framework development", "UI implementation"],
                tools=["React", "Vue", "Angular", "CSS frameworks"],
                questions_to_ask=[
                    "What should the user interface look like?",
                    "What devices need to be supported?",
                    "What are the user experience goals?"
                ],
                artifacts_can_create=["user interfaces", "components", "style guides"]
            ),
            responsibilities=["build user interfaces", "implement designs", "optimize performance"]
        ))

        self._add_expert(DomainExpert(
            job_title="Backend Developer",
            expertise_level=ExpertiseLevel.INTERMEDIATE,
            knowledge_context=KnowledgeContext(
                knowledge_type=KnowledgeType.TECHNICAL,
                topics=["server-side logic", "databases", "APIs", "security"],
                skills=["server programming", "database management", "API development"],
                tools=["Python", "Node.js", "SQL", "NoSQL"],
                questions_to_ask=[
                    "What data needs to be stored?",
                    "How will different parts of the system communicate?",
                    "What security measures are needed?"
                ],
                artifacts_can_create=["API endpoints", "database schemas", "server logic"]
            ),
            responsibilities=["build server logic", "manage databases", "create APIs"]
        ))

        self._add_expert(DomainExpert(
            job_title="Product Designer",
            expertise_level=ExpertiseLevel.INTERMEDIATE,
            knowledge_context=KnowledgeContext(
                knowledge_type=KnowledgeType.CREATIVE,
                topics=["user experience", "visual design", "user research", "prototyping"],
                skills=["design thinking", "prototyping", "user research", "visual design"],
                tools=["Figma", "Sketch", "Adobe XD", "prototyping tools"],
                questions_to_ask=[
                    "Who are the users?",
                    "What problems are we solving for them?",
                    "What should the experience feel like?"
                ],
                artifacts_can_create=["wireframes", "mockups", "prototypes", "design systems"]
            ),
            responsibilities=["design user experience", "create visual designs", "conduct user research"]
        ))

        self._add_expert(DomainExpert(
            job_title="Project Manager",
            expertise_level=ExpertiseLevel.SENIOR,
            knowledge_context=KnowledgeContext(
                knowledge_type=KnowledgeType.MANAGEMENT,
                topics=["project planning", "team coordination", "risk management", "timelines"],
                skills=["planning", "communication", "problem-solving", "team leadership"],
                tools=["project management software", "scheduling tools", "communication platforms"],
                questions_to_ask=[
                    "What is the project timeline?",
                    "What are the project milestones?",
                    "What resources are needed?",
                    "What are the potential risks?"
                ],
                artifacts_can_create=["project plans", "schedules", "status reports", "risk assessments"]
            ),
            responsibilities=["manage project timeline", "coordinate team", "handle risks"]
        ))

        self._add_expert(DomainExpert(
            job_title="Business Analyst",
            expertise_level=ExpertiseLevel.INTERMEDIATE,
            knowledge_context=KnowledgeContext(
                knowledge_type=KnowledgeType.BUSINESS,
                topics=["requirements analysis", "business processes", "stakeholder management"],
                skills=["requirements gathering", "process analysis", "communication"],
                tools=["documentation tools", "diagramming software", "analytics"],
                questions_to_ask=[
                    "What are the business goals?",
                    "Who are the stakeholders?",
                    "What are the success criteria?"
                ],
                artifacts_can_create=["requirements documents", "business process diagrams", "stakeholder analysis"]
            ),
            responsibilities=["gather requirements", "analyze business needs", "document processes"]
        ))

        self._add_expert(DomainExpert(
            job_title="Quality Assurance Engineer",
            expertise_level=ExpertiseLevel.INTERMEDIATE,
            knowledge_context=KnowledgeContext(
                knowledge_type=KnowledgeType.TECHNICAL,
                topics=["testing", "quality assurance", "bug tracking", "automation"],
                skills=["test planning", "test execution", "bug reporting", "test automation"],
                tools=["testing frameworks", "bug trackers", "automation tools"],
                questions_to_ask=[
                    "What needs to be tested?",
                    "How should tests be automated?",
                    "What are the quality standards?"
                ],
                artifacts_can_create=["test plans", "test cases", "bug reports", "test automation scripts"]
            ),
            responsibilities=["create test plans", "execute tests", "report bugs"]
        ))

        self._add_expert(DomainExpert(
            job_title="Data Scientist",
            expertise_level=ExpertiseLevel.EXPERT,
            knowledge_context=KnowledgeContext(
                knowledge_type=KnowledgeType.RESEARCH,
                topics=["data analysis", "machine learning", "statistics", "data visualization"],
                skills=["data analysis", "model building", "statistical analysis", "visualization"],
                tools=["Python", "R", "TensorFlow", "PyTorch", "Tableau"],
                questions_to_ask=[
                    "What data is available?",
                    "What patterns are we looking for?",
                    "How will insights be used?"
                ],
                artifacts_can_create=["data models", "analysis reports", "visualizations", "predictions"]
            ),
            responsibilities=["analyze data", "build models", "create insights"]
        ))

        self._add_expert(DomainExpert(
            job_title="DevOps Engineer",
            expertise_level=ExpertiseLevel.SENIOR,
            knowledge_context=KnowledgeContext(
                knowledge_type=KnowledgeType.OPERATIONS,
                topics=["deployment", "infrastructure", "CI/CD", "monitoring"],
                skills=["deployment automation", "infrastructure management", "monitoring"],
                tools=["Docker", "Kubernetes", "AWS", "Azure", "CI/CD tools"],
                questions_to_ask=[
                    "How will the system be deployed?",
                    "What infrastructure is needed?",
                    "How will we monitor the system?"
                ],
                artifacts_can_create=["deployment pipelines", "infrastructure code", "monitoring dashboards"]
            ),
            responsibilities=["deploy systems", "manage infrastructure", "set up CI/CD"]
        ))

    def _add_expert(self, expert: DomainExpert):
        """Add an expert to the database."""
        self.experts[expert.job_title.lower()] = expert

    def identify_required_experts(self, project_description: str) -> List[DomainExpert]:
        """
        Identify which domain experts are needed for a project based on description.
        Uses keyword matching and context analysis.
        """
        required_experts = []
        description_lower = project_description.lower()

        # Define expert detection patterns
        expert_patterns = {
            "software architect": ["software", "system", "architecture", "technical design", "scalability"],
            "frontend developer": ["frontend", "user interface", "ui", "website", "web app", "visual"],
            "backend developer": ["backend", "server", "api", "database", "data storage"],
            "product designer": ["design", "user experience", "ux", "prototype", "mockup", "visual"],
            "project manager": ["project", "timeline", "schedule", "manage", "coordinate"],
            "business analyst": ["requirements", "business", "stakeholders", "analysis", "needs"],
            "quality assurance engineer": ["test", "quality", "bug", "testing", "qa"],
            "data scientist": ["data", "analytics", "machine learning", "prediction", "patterns"],
            "devops engineer": ["deploy", "deployment", "infrastructure", "cloud", "operations"]
        }

        # Check for patterns in project description
        for expert_name, patterns in expert_patterns.items():
            for pattern in patterns:
                if pattern in description_lower:
                    if expert_name in self.experts:
                        required_experts.append(self.experts[expert_name])
                    break

        return required_experts

    def generate_swarm_proposal(
        self,
        project_description: str,
        complexity: str = "medium"
    ) -> Dict[str, Any]:
        """
        Generate a swarm proposal for executing a project.
        Uses RLM-style decomposition pattern.
        """
        # Identify required experts
        experts = self.identify_required_experts(project_description)

        # If no experts found, provide a default team
        if not experts:
            experts = [
                self.experts["project manager"],
                self.experts["business analyst"],
                self.experts["software architect"]
            ]

        # Generate tasks for each expert
        tasks = []
        for expert in experts:
            # Use expert's knowledge context to generate relevant tasks
            for question in expert.knowledge_context.questions_to_ask:
                tasks.append({
                    "assigned_to": expert.job_title,
                    "task": f"Analyze and answer: {question}",
                    "context": expert.knowledge_context.knowledge_type.value,
                    "priority": "high" if expert.expertise_level == ExpertiseLevel.SENIOR else "medium"
                })

        # Calculate estimated metrics
        estimated_time = len(experts) * 5  # 5 hours per expert base estimate
        if complexity == "simple":
            estimated_time = int(estimated_time * 0.5)
        elif complexity == "complex":
            estimated_time = int(estimated_time * 2)

        estimated_cost = len(experts) * 100  # $100 per hour per expert

        # Generate artifact suggestions
        suggested_artifacts = []
        for expert in experts:
            for artifact_type in expert.knowledge_context.artifacts_can_create:
                suggested_artifacts.append({
                    "type": artifact_type,
                    "created_by": expert.job_title
                })

        return {
            "project_description": project_description,
            "complexity": complexity,
            "required_experts": [e.to_dict() for e in experts],
            "tasks": tasks,
            "estimated_time_hours": estimated_time,
            "estimated_cost_usd": estimated_cost,
            "suggested_artifacts": suggested_artifacts[:10],  # Limit to 10 artifacts
            "confidence_score": 85  # Default confidence score
        }

    def execute_rlm_task(
        self,
        task: str,
        context: Dict[str, Any],
        expert: DomainExpert
    ) -> Dict[str, Any]:
        """
        Execute a task using RLM patterns.
        This simulates the recursive decomposition shown in the paper.
        """
        result = {
            "task": task,
            "expert": expert.job_title,
            "steps": [],
            "artifacts": [],
            "final_answer": None
        }

        # Step 1: Expert analyzes the task using their knowledge context
        result["steps"].append({
            "step": 1,
            "action": "analyze_task",
            "description": f"{expert.job_title} analyzes task using {expert.knowledge_context.knowledge_type.value} knowledge",
            "context_used": expert.knowledge_context.topics
        })

        # Step 2: Break down task into sub-tasks (RLM pattern)
        sub_tasks = []
        for skill in expert.knowledge_context.skills[:3]:  # Use first 3 skills
            sub_tasks.append(f"Apply {skill} to: {task}")

        for i, sub_task in enumerate(sub_tasks, start=2):
            result["steps"].append({
                "step": i,
                "action": "recursive_subtask",
                "description": f"Execute subtask: {sub_task}",
                "using_expertise": expert.knowledge_context.skills[i-2]
            })

        # Step 3: Generate artifact
        if expert.knowledge_context.artifacts_can_create:
            artifact_type = expert.knowledge_context.artifacts_can_create[0]
            artifact = Artifact(
                name=f"{artifact_type} for {task[:30]}",
                type=artifact_type,
                description=f"Generated by {expert.job_title}",
                created_by=expert.job_title,
                content=f"Draft {artifact_type} content for task: {task}"
            )
            result["artifacts"].append(artifact.to_dict())
            result["steps"].append({
                "step": len(sub_tasks) + 2,
                "action": "generate_artifact",
                "description": f"Created {artifact_type}",
                "artifact": artifact.name
            })

        # Step 4: Compile final answer
        result["final_answer"] = f"Task completed by {expert.job_title} using their expertise in {expert.knowledge_context.knowledge_type.value}. Generated {len(result['artifacts'])} artifacts."

        return result

    def get_expert_by_title(self, title: str) -> Optional[DomainExpert]:
        """Get an expert by job title."""
        return self.experts.get(title.lower())

    def list_all_experts(self) -> List[Dict]:
        """List all available experts."""
        return [expert.to_dict() for expert in self.experts.values()]

    def to_dict(self) -> Dict:
        """Convert swarm to dictionary."""
        return {
            "experts": [expert.to_dict() for expert in self.experts.values()],
            "artifacts": [artifact.to_dict() for artifact in self.artifacts.values()]
        }
