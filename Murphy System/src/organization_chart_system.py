"""
Organization Chart System
Parses organization charts and maps job positions to knowledge contexts.
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Department(Enum):
    """Common departments in organizations."""
    ENGINEERING = "engineering"
    DESIGN = "design"
    PRODUCT = "product"
    MARKETING = "marketing"
    SALES = "sales"
    OPERATIONS = "operations"
    FINANCE = "finance"
    HR = "human_resources"
    LEGAL = "legal"
    EXECUTIVE = "executive"


@dataclass
class JobPosition:
    """Represents a job position in an organization."""
    title: str
    department: Department
    level: str  # junior, senior, lead, manager, director, executive
    knowledge_domains: List[str]
    skills: List[str]
    tools_used: List[str]
    typical_tasks: List[str]
    collaboration_needs: List[str]

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "department": self.department.value,
            "level": self.level,
            "knowledge_domains": self.knowledge_domains,
            "skills": self.skills,
            "tools_used": self.tools_used,
            "typical_tasks": self.typical_tasks,
            "collaboration_needs": self.collaboration_needs
        }


@dataclass
class OrgNode:
    """Represents a node in the organization chart."""
    position: JobPosition
    reports: List['OrgNode'] = field(default_factory=list)
    parent: Optional['OrgNode'] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "position": self.position.to_dict(),
            "reports": [node.to_dict() for node in self.reports],
            "parent": self.parent.position.title if self.parent else None
        }


class OrganizationChart:
    """
    Manages organization chart structure and job position mappings.
    Provides knowledge context for each position.
    """

    def __init__(self):
        self.positions: Dict[str, JobPosition] = {}
        self.root_nodes: List[OrgNode] = []
        self._initialize_common_positions()

    def _initialize_common_positions(self):
        """Initialize common job positions across departments."""

        # Engineering Department
        self._add_position(JobPosition(
            title="Software Engineer",
            department=Department.ENGINEERING,
            level="mid",
            knowledge_domains=["programming", "software development", "algorithms", "system design"],
            skills=["coding", "debugging", "testing", "code review"],
            tools_used=["IDEs", "git", "programming languages", "databases"],
            typical_tasks=["write code", "fix bugs", "implement features", "review code"],
            collaboration_needs=["product managers", "designers", "other engineers", "QA"]
        ))

        self._add_position(JobPosition(
            title="Senior Software Engineer",
            department=Department.ENGINEERING,
            level="senior",
            knowledge_domains=["architecture", "scalability", "performance", "mentoring"],
            skills=["system design", "technical leadership", "code review", "mentoring"],
            tools_used=["architecture tools", "cloud platforms", "development tools"],
            typical_tasks=["design architecture", "lead projects", "mentor junior engineers", "make technical decisions"],
            collaboration_needs=["engineering managers", "product managers", "architects", "stakeholders"]
        ))

        self._add_position(JobPosition(
            title="Engineering Manager",
            department=Department.ENGINEERING,
            level="manager",
            knowledge_domains=["team management", "project delivery", "technical oversight", "hiring"],
            skills=["leadership", "planning", "communication", "technical decision making"],
            tools_used=["project management tools", "hiring platforms", "communication tools"],
            typical_tasks=["manage team", "plan projects", "conduct reviews", "hire engineers"],
            collaboration_needs=["senior engineers", "product managers", "other managers", "HR"]
        ))

        # Design Department
        self._add_position(JobPosition(
            title="Product Designer",
            department=Department.DESIGN,
            level="mid",
            knowledge_domains=["user experience", "visual design", "user research", "interaction design"],
            skills=["design thinking", "prototyping", "user research", "visual design"],
            tools_used=["Figma", "Sketch", "Adobe XD", "prototyping tools"],
            typical_tasks=["create designs", "conduct user research", "build prototypes", "collaborate with developers"],
            collaboration_needs=["product managers", "engineers", "other designers", "stakeholders"]
        ))

        self._add_position(JobPosition(
            title="Design Lead",
            department=Department.DESIGN,
            level="senior",
            knowledge_domains=["design systems", "design strategy", "team leadership", "design operations"],
            skills=["design leadership", "design systems", "mentoring", "strategic thinking"],
            tools_used=["design tools", "documentation tools", "presentation tools"],
            typical_tasks=["lead design team", "create design systems", "define design strategy", "mentor designers"],
            collaboration_needs=["product managers", "engineering leads", "stakeholders", "design team"]
        ))

        # Product Department
        self._add_position(JobPosition(
            title="Product Manager",
            department=Department.PRODUCT,
            level="mid",
            knowledge_domains=["product strategy", "user needs", "market analysis", "roadmapping"],
            skills=["requirements gathering", "prioritization", "communication", "analytical thinking"],
            tools_used=["product management tools", "analytics", "documentation tools"],
            typical_tasks=["define product requirements", "create roadmaps", "prioritize features", "work with teams"],
            collaboration_needs=["engineers", "designers", "stakeholders", "business teams"]
        ))

        self._add_position(JobPosition(
            title="Senior Product Manager",
            department=Department.PRODUCT,
            level="senior",
            knowledge_domains=["product strategy", "business metrics", "market positioning", "team leadership"],
            skills=["strategic thinking", "leadership", "analytics", "communication"],
            tools_used=["analytics platforms", "strategy tools", "presentation tools"],
            typical_tasks=["define product strategy", "analyze metrics", "lead product initiatives", "mentor PMs"],
            collaboration_needs=["engineering leads", "design leads", "executives", "cross-functional teams"]
        ))

        # Marketing Department
        self._add_position(JobPosition(
            title="Marketing Specialist",
            department=Department.MARKETING,
            level="mid",
            knowledge_domains=["marketing strategy", "content creation", "campaigns", "analytics"],
            skills=["copywriting", "campaign management", "analytics", "social media"],
            tools_used=["marketing platforms", "analytics tools", "content management"],
            typical_tasks=["create marketing materials", "run campaigns", "analyze results", "create content"],
            collaboration_needs=["product managers", "designers", "sales team", "external partners"]
        ))

        # Sales Department
        self._add_position(JobPosition(
            title="Sales Representative",
            department=Department.SALES,
            level="mid",
            knowledge_domains=["sales", "customer relationships", "negotiation", "product knowledge"],
            skills=["communication", "negotiation", "relationship building", "presentation"],
            tools_used=["CRM systems", "sales tools", "communication platforms"],
            typical_tasks=["sell products", "manage relationships", "close deals", "present to clients"],
            collaboration_needs=["marketing team", "product team", "sales managers", "customers"]
        ))

        # Operations Department
        self._add_position(JobPosition(
            title="Operations Coordinator",
            department=Department.OPERATIONS,
            level="mid",
            knowledge_domains=["operations", "processes", "logistics", "efficiency"],
            skills=["process improvement", "coordination", "problem-solving", "organization"],
            tools_used=["operations software", "project management tools", "documentation"],
            typical_tasks=["coordinate operations", "improve processes", "manage logistics", "track metrics"],
            collaboration_needs=["all departments", "vendors", "management", "teams"]
        ))

        # Executive Level
        self._add_position(JobPosition(
            title="CTO (Chief Technology Officer)",
            department=Department.EXECUTIVE,
            level="executive",
            knowledge_domains=["technology strategy", "technical leadership", "innovation", "business alignment"],
            skills=["strategic thinking", "technical leadership", "business acumen", "team building"],
            tools_used=["strategic tools", "communication platforms", "analytics"],
            typical_tasks=["define tech strategy", "lead technical vision", "make strategic decisions", "build engineering culture"],
            collaboration_needs=["other executives", "engineering leaders", "board", "stakeholders"]
        ))

        self._add_position(JobPosition(
            title="CPO (Chief Product Officer)",
            department=Department.EXECUTIVE,
            level="executive",
            knowledge_domains=["product strategy", "business growth", "user experience", "market positioning"],
            skills=["strategic thinking", "leadership", "analytics", "communication"],
            tools_used=["strategy tools", "analytics", "presentation tools"],
            typical_tasks=["define product strategy", "drive product vision", "align with business goals", "lead product organization"],
            collaboration_needs=["other executives", "product leaders", "engineering leaders", "board"]
        ))

    def _add_position(self, position: JobPosition):
        """Add a position to the organization."""
        self.positions[position.title.lower()] = position

    def get_position(self, title: str) -> Optional[JobPosition]:
        """Get a position by title."""
        return self.positions.get(title.lower())

    def search_positions_by_skill(self, skill: str) -> List[JobPosition]:
        """Search for positions that have a specific skill."""
        skill_lower = skill.lower()
        return [
            pos for pos in self.positions.values()
            if any(skill_lower in s.lower() for s in pos.skills)
        ]

    def search_positions_by_department(self, department: Department) -> List[JobPosition]:
        """Search for positions in a specific department."""
        return [
            pos for pos in self.positions.values()
            if pos.department == department
        ]

    def get_knowledge_context_for_project(
        self,
        project_description: str
    ) -> Dict[str, Any]:
        """
        Determine the knowledge context needed for a project.
        Analyzes project description and maps to relevant positions.
        """
        description_lower = project_description.lower()

        # Map project keywords to positions
        position_mapping = {
            "software engineer": ["software", "code", "develop", "programming", "technical"],
            "senior software engineer": ["architecture", "scalable", "system", "technical lead"],
            "product designer": ["design", "ui", "ux", "visual", "interface"],
            "product manager": ["product", "requirements", "features", "roadmap"],
            "marketing specialist": ["marketing", "campaign", "content", "brand"],
            "sales representative": ["sales", "customers", "deals", "revenue"],
            "operations coordinator": ["operations", "process", "logistics", "efficiency"],
            "cto": ["technology strategy", "technical vision", "innovation"],
            "cpo": ["product strategy", "business growth", "market"]
        }

        required_positions = []
        for position_title, keywords in position_mapping.items():
            if any(keyword in description_lower for keyword in keywords):
                position = self.get_position(position_title)
                if position:
                    required_positions.append(position)

        # If no positions found, provide defaults
        if not required_positions:
            required_positions = [
                self.get_position("Product Manager"),
                self.get_position("Software Engineer"),
                self.get_position("Product Designer")
            ]

        # Aggregate knowledge context
        knowledge_context = {
            "required_positions": [pos.to_dict() for pos in required_positions],
            "aggregated_knowledge_domains": list(set(
                domain for pos in required_positions
                for domain in pos.knowledge_domains
            )),
            "aggregated_skills": list(set(
                skill for pos in required_positions
                for skill in pos.skills
            ))[:20],  # Limit to 20 skills
            "tools_needed": list(set(
                tool for pos in required_positions
                for tool in pos.tools_used
            ))[:15],  # Limit to 15 tools
            "typical_tasks": list(set(
                task for pos in required_positions
                for task in pos.typical_tasks
            ))[:15],  # Limit to 15 tasks
            "collaboration_map": self._build_collaboration_map(required_positions)
        }

        return knowledge_context

    def _build_collaboration_map(
        self,
        positions: List[JobPosition]
    ) -> Dict[str, List[str]]:
        """Build a collaboration map showing who needs to work with whom."""
        collaboration_map = {}

        for position in positions:
            collaboration_map[position.title] = position.collaboration_needs

        return collaboration_map

    def list_all_departments(self) -> List[str]:
        """List all departments."""
        return [dept.value for dept in Department]

    def list_all_positions(self) -> List[Dict]:
        """List all positions."""
        return [pos.to_dict() for pos in self.positions.values()]

    def to_dict(self) -> Dict:
        """Convert organization chart to dictionary."""
        return {
            "positions": [pos.to_dict() for pos in self.positions.values()],
            "departments": self.list_all_departments()
        }
