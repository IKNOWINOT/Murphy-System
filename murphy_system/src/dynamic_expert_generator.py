"""
Dynamic Expert Generation System
Generates domain experts dynamically based on system requirements
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("dynamic_expert_generator")


class ExpertLevel(Enum):
    """Expert seniority levels"""
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    PRINCIPAL = "principal"
    EXPERT = "expert"


@dataclass
class ExpertCapability:
    """Represents a single expert capability"""
    name: str
    proficiency: float  # 0.0 to 1.0
    years_experience: int
    certified: bool = False
    tools: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "proficiency": self.proficiency,
            "years_experience": self.years_experience,
            "certified": self.certified,
            "tools": self.tools
        }


@dataclass
class ExpertKnowledge:
    """Knowledge domains for an expert"""
    domains: List[str] = field(default_factory=list)
    specialized_areas: List[str] = field(default_factory=list)
    best_practices: List[str] = field(default_factory=list)
    regulatory_knowledge: List[str] = field(default_factory=list)
    architectural_patterns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "domains": self.domains,
            "specialized_areas": self.specialized_areas,
            "best_practices": self.best_practices,
            "regulatory_knowledge": self.regulatory_knowledge,
            "architectural_patterns": self.architectural_patterns
        }


@dataclass
class ExpertArtifact:
    """Types of artifacts an expert can create or modify"""
    artifact_type: str
    creation: bool = True
    modification: bool = True
    review: bool = True
    examples: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "artifact_type": self.artifact_type,
            "creation": self.creation,
            "modification": self.modification,
            "review": self.review,
            "examples": self.examples
        }


@dataclass
class GeneratedExpert:
    """Dynamically generated expert"""
    id: str
    name: str
    title: str
    level: ExpertLevel
    capabilities: List[ExpertCapability]
    knowledge: ExpertKnowledge
    artifacts: List[ExpertArtifact]
    system_logic_effects: List[str] = field(default_factory=list)
    confidence_threshold: float = 0.85
    cost_per_hour: float = 0.0
    availability: float = 1.0  # 0.0 to 1.0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "title": self.title,
            "level": self.level.value,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "knowledge": self.knowledge.to_dict(),
            "artifacts": [a.to_dict() for a in self.artifacts],
            "system_logic_effects": self.system_logic_effects,
            "confidence_threshold": self.confidence_threshold,
            "cost_per_hour": self.cost_per_hour,
            "availability": self.availability,
            "expert": self.name,
        }

    def __contains__(self, item):
        """Support 'in' operator for dict-like field access"""
        return hasattr(self, item) or item in self.to_dict()


class DynamicExpertGenerator:
    """
    Generates domain experts dynamically based on system requirements
    Uses templates and LLM prompts to create specialized experts
    """

    def __init__(self):
        self.expert_count = 0
        self.expert_templates = self._load_expert_templates()
        self.domain_knowledge = self._load_domain_knowledge()

    def _load_expert_templates(self) -> Dict:
        """Load expert templates for common roles"""
        return {
            "software_developer": {
                "capabilities": ["programming", "debugging", "code_review", "testing"],
                "knowledge": ["software_patterns", "algorithms", "data_structures"],
                "artifacts": ["code", "tests", "documentation"]
            },
            "architect": {
                "capabilities": ["system_design", "pattern_selection", "scalability_planning"],
                "knowledge": ["architectural_patterns", "design_principles", "integration"],
                "artifacts": ["architecture_diagrams", "design_docs", "api_specs"]
            },
            "security_specialist": {
                "capabilities": ["threat_modeling", "security_testing", "compliance"],
                "knowledge": ["security_standards", "vulnerabilities", "encryption"],
                "artifacts": ["security_reports", "compliance_docs", "threat_models"]
            },
            "data_scientist": {
                "capabilities": ["data_analysis", "ml_modeling", "statistical_analysis"],
                "knowledge": ["ml_algorithms", "statistics", "data_visualization"],
                "artifacts": ["models", "reports", "datasets"]
            },
            "devops_engineer": {
                "capabilities": ["deployment", "monitoring", "automation", "scaling"],
                "knowledge": ["cloud_platforms", "cicd", "infrastructure"],
                "artifacts": ["deployment_scripts", "monitoring_dashboards", "playbooks"]
            }
        }

    def _load_domain_knowledge(self) -> Dict:
        """Load knowledge about different domains"""
        return {
            "software": {
                "best_practices": ["clean_code", "solid_principles", "tdd", "ci_cd"],
                "regulatory": ["gdpr", "hipaa", "pci_dss", "soc2"],
                "architectural": ["microservices", "monolith", "serverless", "event_driven"]
            },
            "infrastructure": {
                "best_practices": ["infrastructure_as_code", "immutable_infrastructure", "monitoring"],
                "regulatory": ["iso27001", "nist_csf"],
                "architectural": ["cloud_native", "hybrid", "multi_cloud"]
            },
            "data": {
                "best_practices": ["data_governance", "quality_checks", "privacy_by_design"],
                "regulatory": ["gdpr", "ccpa", "data_localization"],
                "architectural": ["data_lake", "data_warehouse", "streaming"]
            }
        }

    def generate_expert(
        self,
        title: str = None,
        domain: str = None,
        level: str = "mid",
        specializations: List[str] = None,
        budget_constraint: Optional[float] = None,
        regulatory_requirements: List[str] = None,
        architectural_requirements: List[str] = None,
        *,
        specialization: str = None,
    ) -> GeneratedExpert:
        """
        Generate a dynamic expert based on requirements

        Args:
            title: Expert title (e.g., "Backend Developer", "Security Architect")
            domain: Domain (e.g., "software", "infrastructure", "data")
            level: Expert level (junior, mid, senior, principal, expert)
            specializations: List of specialization areas
            specialization: Single specialization (convenience alias)
            budget_constraint: Maximum hourly rate
            regulatory_requirements: Required regulatory knowledge
            architectural_requirements: Required architectural knowledge

        Returns:
            GeneratedExpert object or dict with expert key
        """
        # Handle convenience aliases
        if specialization and not specializations:
            specializations = [specialization]
        if title is None:
            title = f"{domain or 'General'} {specialization or 'Expert'}"
        if domain is None:
            domain = "software"
        self.expert_count += 1
        expert_id = f"expert_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{self.expert_count}"

        # Map level string to enum
        level_enum = ExpertLevel(level.lower())

        # Generate capabilities
        capabilities = self._generate_capabilities(
            title, domain, level_enum, specializations
        )

        # Generate knowledge
        knowledge = self._generate_knowledge(
            domain, level_enum, regulatory_requirements, architectural_requirements
        )

        # Generate artifacts
        artifacts = self._generate_artifacts(title, domain)

        # Calculate cost based on level and capabilities
        cost_per_hour = self._calculate_cost(level_enum, capabilities, budget_constraint)

        # Determine confidence threshold
        confidence_threshold = self._calculate_confidence_threshold(level_enum)

        # Create expert
        expert = GeneratedExpert(
            id=expert_id,
            name=title.replace("_", " ").title(),
            title=title,
            level=level_enum,
            capabilities=capabilities,
            knowledge=knowledge,
            artifacts=artifacts,
            system_logic_effects=self._determine_system_logic_effects(domain, title),
            confidence_threshold=confidence_threshold,
            cost_per_hour=cost_per_hour,
            availability=1.0
        )

        return expert

    def _generate_capabilities(
        self,
        title: str,
        domain: str,
        level: ExpertLevel,
        specializations: List[str] = None
    ) -> List[ExpertCapability]:
        """Generate expert capabilities based on title, domain, and level"""
        capabilities = []

        # Get base capabilities from template or create from title
        template_key = title.lower().replace(" ", "_")
        if template_key in self.expert_templates:
            base_caps = self.expert_templates[template_key]["capabilities"]
        else:
            base_caps = self._derive_capabilities_from_title(title)

        # Generate capability objects with proficiency based on level
        level_proficiency = {
            ExpertLevel.JUNIOR: 0.4,
            ExpertLevel.MID: 0.6,
            ExpertLevel.SENIOR: 0.8,
            ExpertLevel.PRINCIPAL: 0.9,
            ExpertLevel.EXPERT: 0.95
        }

        base_prof = level_proficiency[level]
        years_exp = {
            ExpertLevel.JUNIOR: 1,
            ExpertLevel.MID: 3,
            ExpertLevel.SENIOR: 7,
            ExpertLevel.PRINCIPAL: 12,
            ExpertLevel.EXPERT: 15
        }[level]

        for cap in base_caps:
            proficiency = base_prof + (0.05 if specializations and cap in specializations else 0)
            capabilities.append(ExpertCapability(
                name=cap,
                proficiency=min(1.0, proficiency),
                years_experience=years_exp,
                certified=level in [ExpertLevel.SENIOR, ExpertLevel.PRINCIPAL, ExpertLevel.EXPERT],
                tools=self._get_tools_for_capability(cap, domain)
            ))

        # Add specializations
        if specializations:
            for spec in specializations:
                if spec not in [c.name for c in capabilities]:
                    capabilities.append(ExpertCapability(
                        name=spec,
                        proficiency=base_prof + 0.1,
                        years_experience=years_exp,
                        certified=True,
                        tools=self._get_tools_for_capability(spec, domain)
                    ))

        return capabilities

    def _derive_capabilities_from_title(self, title: str) -> List[str]:
        """Derive capabilities from expert title"""
        title_lower = title.lower()

        capability_mapping = {
            "developer": ["programming", "debugging", "code_review", "testing"],
            "architect": ["system_design", "pattern_selection", "scalability_planning", "integration"],
            "engineer": ["engineering", "implementation", "optimization", "maintenance"],
            "specialist": ["specialized_knowledge", "analysis", "consultation"],
            "analyst": ["analysis", "data_interpretation", "reporting", "insights"],
            "manager": ["planning", "coordination", "communication", "oversight"],
            "designer": ["design", "prototyping", "user_experience", "visual_composition"],
            "consultant": ["consultation", "strategy", "recommendations", "guidance"]
        }

        derived = []
        for keyword, caps in capability_mapping.items():
            if keyword in title_lower:
                derived.extend(caps)

        return derived if derived else ["general_knowledge", "problem_solving", "communication"]

    def _get_tools_for_capability(self, capability: str, domain: str) -> List[str]:
        """Get relevant tools for a capability"""
        tool_mapping = {
            "programming": ["git", "ide", "debugger", "testing_framework"],
            "system_design": ["architecture_tools", "diagramming", "modeling"],
            "security": ["vulnerability_scanner", "penetration_testing", "compliance_tools"],
            "data_analysis": ["python", "sql", "visualization_tools", "ml_frameworks"],
            "deployment": ["docker", "kubernetes", "ci_cd", "cloud_cli"],
            "monitoring": ["monitoring_tools", "logging", "alerting"],
            "testing": ["testing_frameworks", "automation", "mocking"]
        }

        return tool_mapping.get(capability.lower(), ["general_tools"])

    def _generate_knowledge(
        self,
        domain: str,
        level: ExpertLevel,
        regulatory_requirements: List[str] = None,
        architectural_requirements: List[str] = None
    ) -> ExpertKnowledge:
        """Generate knowledge domains for expert"""
        domain_data = self.domain_knowledge.get(domain, {})

        # Base knowledge from domain
        best_practices = domain_data.get("best_practices", [])
        regulatory = domain_data.get("regulatory", [])
        architectural = domain_data.get("architectural", [])

        # Add custom requirements
        if regulatory_requirements:
            regulatory.extend(regulatory_requirements)

        if architectural_requirements:
            architectural.extend(architectural_requirements)

        # Generate specialized areas based on level
        specialized_areas = []
        if level in [ExpertLevel.SENIOR, ExpertLevel.PRINCIPAL, ExpertLevel.EXPERT]:
            specialized_areas = [
                f"advanced_{domain}_patterns",
                "mentoring",
                "architecture_review"
            ]

        return ExpertKnowledge(
            domains=[domain],
            specialized_areas=specialized_areas,
            best_practices=best_practices,
            regulatory_knowledge=list(set(regulatory)),
            architectural_patterns=list(set(architectural))
        )

    def _generate_artifacts(self, title: str, domain: str) -> List[ExpertArtifact]:
        """Generate artifact types for expert"""
        title_lower = title.lower()

        # Common artifact mappings
        artifact_mapping = {
            "developer": [
                ExpertArtifact("source_code"),
                ExpertArtifact("unit_tests"),
                ExpertArtifact("technical_documentation")
            ],
            "architect": [
                ExpertArtifact("architecture_diagram"),
                ExpertArtifact("design_document"),
                ExpertArtifact("api_specification")
            ],
            "engineer": [
                ExpertArtifact("implementation_plan"),
                ExpertArtifact("configuration"),
                ExpertArtifact("deployment_scripts")
            ],
            "analyst": [
                ExpertArtifact("analysis_report"),
                ExpertArtifact("data_insights"),
                ExpertArtifact("recommendations")
            ],
            "manager": [
                ExpertArtifact("project_plan"),
                ExpertArtifact("status_reports"),
                ExpertArtifact("resource_allocation")
            ]
        }

        for keyword, artifacts in artifact_mapping.items():
            if keyword in title_lower:
                return artifacts

        # Default artifacts
        return [
            ExpertArtifact("documentation"),
            ExpertArtifact("reports"),
            ExpertArtifact("recommendations")
        ]

    def _determine_system_logic_effects(self, domain: str, title: str) -> List[str]:
        """Determine what system logic the expert affects"""
        effects = []

        domain_effects = {
            "software": [
                "code_quality",
                "development_velocity",
                "technical_debt",
                "system_reliability"
            ],
            "infrastructure": [
                "system_availability",
                "scalability",
                "deployment_speed",
                "operational_cost"
            ],
            "data": [
                "data_quality",
                "analytics_accuracy",
                "ml_model_performance",
                "data_governance"
            ]
        }

        effects.extend(domain_effects.get(domain, []))

        # Title-specific effects
        if "security" in title.lower():
            effects.extend(["security_posture", "compliance_status", "vulnerability_management"])

        if "architect" in title.lower():
            effects.extend(["system_architecture", "technical_direction", "design_consistency"])

        return list(set(effects))

    def _calculate_cost(
        self,
        level: ExpertLevel,
        capabilities: List[ExpertCapability],
        budget_constraint: Optional[float]
    ) -> float:
        """Calculate hourly cost based on level and capabilities"""
        base_rates = {
            ExpertLevel.JUNIOR: 50,
            ExpertLevel.MID: 85,
            ExpertLevel.SENIOR: 125,
            ExpertLevel.PRINCIPAL: 175,
            ExpertLevel.EXPERT: 250
        }

        base_rate = base_rates[level]

        # Add premium for certifications
        premium = sum(10 for cap in capabilities if cap.certified)

        # Add premium for high proficiency
        proficiency_bonus = sum(5 for cap in capabilities if cap.proficiency > 0.8)

        total = base_rate + premium + proficiency_bonus

        # Apply budget constraint if specified
        if budget_constraint:
            total = min(total, budget_constraint)

        return total

    def _calculate_confidence_threshold(self, level: ExpertLevel) -> float:
        """Calculate confidence threshold for expert"""
        thresholds = {
            ExpertLevel.JUNIOR: 0.70,
            ExpertLevel.MID: 0.80,
            ExpertLevel.SENIOR: 0.85,
            ExpertLevel.PRINCIPAL: 0.90,
            ExpertLevel.EXPERT: 0.95
        }
        return thresholds[level]

    def get_available_domains(self) -> list:
        """Get list of available domain names"""
        return list(self.domain_knowledge.keys())

    def generate_expert_team(
        self,
        requirements: Dict[str, Any],
        budget: Optional[float] = None
    ) -> Tuple[List[GeneratedExpert], Dict[str, Any]]:
        """
        Generate a team of experts based on system requirements

        Args:
            requirements: System requirements dict
            budget: Total budget constraint

        Returns:
            Tuple of (expert_list, team_analysis)
        """
        experts = []
        total_cost = 0

        # Extract key requirements
        domain = requirements.get("domain", "software")
        complexity = requirements.get("complexity", "medium")
        team_size = self._determine_team_size(complexity)

        # Determine required expert types
        expert_types = self._determine_expert_types(domain, complexity, requirements)

        # Generate each expert
        for expert_type in expert_types:
            expert_budget = budget / (len(expert_types) or 1) if budget else None

            expert = self.generate_expert(
                title=expert_type["title"],
                domain=domain,
                level=expert_type.get("level", "mid"),
                specializations=expert_type.get("specializations"),
                budget_constraint=expert_budget,
                regulatory_requirements=requirements.get("regulatory_requirements"),
                architectural_requirements=requirements.get("architectural_requirements")
            )

            experts.append(expert)
            total_cost += expert.cost_per_hour

        # Generate team analysis
        team_analysis = {
            "total_experts": len(experts),
            "total_cost_per_hour": total_cost,
            "average_confidence": sum(e.confidence_threshold for e in experts) / (len(experts) or 1),
            "coverage": self._calculate_team_coverage(experts, requirements),
            "budget_utilization": total_cost / budget if budget else None,
            "expertise_distribution": self._calculate_expertise_distribution(experts)
        }

        return experts, team_analysis

    def _determine_team_size(self, complexity: str) -> int:
        """Determine optimal team size based on complexity"""
        sizes = {
            "simple": 2,
            "medium": 4,
            "complex": 6,
            "very_complex": 8
        }
        return sizes.get(complexity.lower(), 4)

    def _determine_expert_types(
        self,
        domain: str,
        complexity: str,
        requirements: Dict
    ) -> List[Dict]:
        """Determine what types of experts are needed"""
        expert_types = []

        # Domain-specific base experts
        if domain == "software":
            expert_types.append({"title": "Software Architect", "level": "senior"})
            expert_types.append({"title": "Backend Developer", "level": "mid"})
            expert_types.append({"title": "Frontend Developer", "level": "mid"})
            if complexity in ["complex", "very_complex"]:
                expert_types.append({"title": "Security Specialist", "level": "senior"})

        elif domain == "infrastructure":
            expert_types.append({"title": "Cloud Architect", "level": "senior"})
            expert_types.append({"title": "DevOps Engineer", "level": "mid"})
            expert_types.append({"title": "Security Engineer", "level": "senior"})
            if complexity in ["complex", "very_complex"]:
                expert_types.append({"title": "Network Engineer", "level": "mid"})

        elif domain == "data":
            expert_types.append({"title": "Data Architect", "level": "senior"})
            expert_types.append({"title": "Data Scientist", "level": "mid"})
            expert_types.append({"title": "Data Engineer", "level": "mid"})
            if complexity in ["complex", "very_complex"]:
                expert_types.append({"title": "ML Engineer", "level": "senior"})

        # Add specialists based on requirements
        if requirements.get("security_focus"):
            expert_types.append({"title": "Security Specialist", "level": "senior"})

        if requirements.get("ml_focus"):
            expert_types.append({"title": "ML Engineer", "level": "senior"})

        return expert_types

    def _calculate_team_coverage(
        self,
        experts: List[GeneratedExpert],
        requirements: Dict
    ) -> Dict[str, float]:
        """Calculate how well the team covers requirements"""
        # Aggregate all capabilities
        all_capabilities = {}
        for expert in experts:
            for cap in expert.capabilities:
                if cap.name not in all_capabilities:
                    all_capabilities[cap.name] = 0.0
                all_capabilities[cap.name] = max(all_capabilities[cap.name], cap.proficiency)

        # Calculate average coverage
        coverage = {
            "capability_coverage": sum(all_capabilities.values()) / (len(all_capabilities) or 1),
            "expert_count": len(experts),
            "unique_capabilities": len(all_capabilities)
        }

        return coverage

    def _calculate_expertise_distribution(
        self,
        experts: List[GeneratedExpert]
    ) -> Dict[str, int]:
        """Calculate distribution of expertise levels"""
        distribution = {}
        for expert in experts:
            level = expert.level.value
            distribution[level] = distribution.get(level, 0) + 1
        return distribution


def create_expert_from_description(
    description: str,
    domain: str = "software",
    budget: Optional[float] = None
) -> GeneratedExpert:
    """
    Create an expert from a natural language description
    This would typically use LLM generation in production

    Args:
        description: Natural language description of expert needed
        domain: Domain (software, infrastructure, data)
        budget: Budget constraint

    Returns:
        GeneratedExpert object
    """
    generator = DynamicExpertGenerator()

    # Simple keyword extraction (would use LLM in production)
    description_lower = description.lower()

    # Extract level
    level = "mid"
    if "senior" in description_lower:
        level = "senior"
    elif "junior" in description_lower:
        level = "junior"
    elif "principal" in description_lower or "lead" in description_lower:
        level = "principal"

    # Extract title (simplified)
    title = "General Developer"
    if "architect" in description_lower:
        title = "Software Architect"
    elif "security" in description_lower:
        title = "Security Specialist"
    elif "data" in description_lower:
        title = "Data Scientist"
    elif "devops" in description_lower:
        title = "DevOps Engineer"
    elif "frontend" in description_lower:
        title = "Frontend Developer"
    elif "backend" in description_lower:
        title = "Backend Developer"

    # Extract specializations
    specializations = []
    if "python" in description_lower:
        specializations.append("python")
    if "javascript" in description_lower:
        specializations.append("javascript")
    if "cloud" in description_lower:
        specializations.append("cloud")
    if "ml" in description_lower or "machine learning" in description_lower:
        specializations.append("machine_learning")

    return generator.generate_expert(
        title=title,
        domain=domain,
        level=level,
        specializations=specializations if specializations else None,
        budget_constraint=budget
    )


if __name__ == "__main__":
    # Test dynamic expert generation
    generator = DynamicExpertGenerator()

    # Test 1: Generate single expert
    logger.info("=== Test 1: Generate Single Expert ===")
    expert = generator.generate_expert(
        title="Software Architect",
        domain="software",
        level="senior",
        specializations=["cloud", "microservices"],
        regulatory_requirements=["gdpr"],
        architectural_requirements=["microservices", "event_driven"]
    )
    logger.info(json.dumps(expert.to_dict(), indent=2))

    # Test 2: Generate expert team
    logger.info("\n=== Test 2: Generate Expert Team ===")
    requirements = {
        "domain": "software",
        "complexity": "complex",
        "security_focus": True,
        "regulatory_requirements": ["gdpr", "hipaa"],
        "architectural_requirements": ["microservices"]
    }

    experts, analysis = generator.generate_expert_team(requirements, budget=1000)
    logger.info(f"Team Size: {analysis['total_experts']}")
    logger.info(f"Total Cost: ${analysis['total_cost_per_hour']}/hour")
    logger.info(f"Avg Confidence: {analysis['average_confidence']:.2%}")
    logger.info(f"Coverage: {analysis['coverage']}")
    logger.info(f"Budget Utilization: {analysis['budget_utilization']:.2%}" if analysis['budget_utilization'] else "No budget")

    # Test 3: Create from description
    logger.info("\n=== Test 3: Create Expert from Description ===")
    expert = create_expert_from_description(
        "I need a senior security specialist with cloud experience",
        domain="software",
        budget=200
    )
    logger.info(json.dumps(expert.to_dict(), indent=2))
