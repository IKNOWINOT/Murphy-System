"""
Domain Expert Integration with Murphy System
Integrates organization charts, domain experts, and RLM patterns with the existing Murphy System.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from domain_expert_system import Artifact, DomainExpert, DomainExpertSwarm, KnowledgeContext
from organization_chart_system import Department, JobPosition, OrganizationChart

logger = logging.getLogger(__name__)


@dataclass
class SwarmExecutionPlan:
    """Represents a complete execution plan for a domain expert swarm."""
    project_description: str
    complexity: str
    experts: List[Dict]
    knowledge_context: Dict
    tasks: List[Dict]
    artifacts: List[Dict]
    collaboration_map: Dict[str, List[str]]
    estimated_metrics: Dict[str, Any]
    rlm_decomposition: List[Dict]


class DomainExpertIntegrator:
    """
    Integrates domain expert swarms with the Murphy System.
    Provides automatic expert selection, knowledge mapping, and task decomposition.
    """

    def __init__(self):
        self.swarm = DomainExpertSwarm()
        self.org_chart = OrganizationChart()
        self.execution_history: List[SwarmExecutionPlan] = []

    def analyze_project_request(
        self,
        user_input: str
    ) -> Dict[str, Any]:
        """
        Analyze a user's project request and generate a comprehensive plan.
        This is the main entry point for domain expert swarm generation.
        """
        # Determine project complexity
        complexity = self._determine_complexity(user_input)

        # Get knowledge context from organization chart
        knowledge_context = self.org_chart.get_knowledge_context_for_project(user_input)

        # Generate swarm proposal
        swarm_proposal = self.swarm.generate_swarm_proposal(user_input, complexity)

        # Generate RLM-style task decomposition
        rlm_decomposition = self._generate_rlm_decomposition(
            user_input,
            swarm_proposal["required_experts"]
        )

        # Create execution plan
        execution_plan = SwarmExecutionPlan(
            project_description=user_input,
            complexity=complexity,
            experts=swarm_proposal["required_experts"],
            knowledge_context=knowledge_context,
            tasks=swarm_proposal["tasks"],
            artifacts=swarm_proposal["suggested_artifacts"],
            collaboration_map=knowledge_context["collaboration_map"],
            estimated_metrics={
                "time_hours": swarm_proposal["estimated_time_hours"],
                "cost_usd": swarm_proposal["estimated_cost_usd"],
                "confidence_score": swarm_proposal["confidence_score"]
            },
            rlm_decomposition=rlm_decomposition
        )

        # Store execution plan
        self.execution_history.append(execution_plan)

        # Format response for user (10-year-old reading level)
        return self._format_user_friendly_response(execution_plan)

    def _determine_complexity(self, user_input: str) -> str:
        """Determine project complexity based on user input."""
        input_lower = user_input.lower()

        simple_indicators = [
            "simple", "basic", "easy", "small", "quick", "minimum"
        ]

        complex_indicators = [
            "complex", "advanced", "enterprise", "scalable", "large",
            "comprehensive", "full-featured", "production-grade"
        ]

        if any(indicator in input_lower for indicator in simple_indicators):
            return "simple"
        elif any(indicator in input_lower for indicator in complex_indicators):
            return "complex"
        else:
            return "medium"

    def _generate_rlm_decomposition(
        self,
        project_description: str,
        experts: List[Dict]
    ) -> List[Dict]:
        """
        Generate RLM-style task decomposition.
        This follows the pattern from the paper: analyze, decompose, execute recursively.
        """
        decomposition = []

        # Level 1: High-level project analysis
        decomposition.append({
            "level": 1,
            "type": "project_analysis",
            "description": "Analyze the overall project requirements and scope",
            "expert": "Project Manager" if any(e["job_title"] == "Project Manager" for e in experts) else experts[0]["job_title"],
            "subtasks": self._generate_analysis_subtasks(project_description)
        })

        # Level 2: Domain-specific decomposition
        for expert in experts[:5]:  # Limit to first 5 experts
            decomposition.append({
                "level": 2,
                "type": "domain_analysis",
                "description": f"Analyze from {expert['job_title']} perspective",
                "expert": expert["job_title"],
                "knowledge_context": expert["knowledge_context"],
                "subtasks": self._generate_domain_subtasks(expert)
            })

        # Level 3: Artifact generation
        for expert in experts[:3]:  # Limit to first 3 experts for artifacts
            artifacts = expert["knowledge_context"]["artifacts_can_create"]
            if artifacts:
                decomposition.append({
                    "level": 3,
                    "type": "artifact_generation",
                    "description": f"Generate artifacts as {expert['job_title']}",
                    "expert": expert["job_title"],
                    "artifacts": artifacts[:2]  # Limit to 2 artifacts per expert
                })

        return decomposition

    def _generate_analysis_subtasks(self, project_description: str) -> List[Dict]:
        """Generate analysis subtasks following RLM pattern."""
        return [
            {
                "step": 1,
                "action": "context_loading",
                "description": "Load project description into context",
                "pattern": "repl_context_load"
            },
            {
                "step": 2,
                "action": "keyword_analysis",
                "description": "Extract key requirements from description",
                "pattern": "regex_matching"
            },
            {
                "step": 3,
                "action": "scope_definition",
                "description": "Define project scope and boundaries",
                "pattern": "llm_query"
            }
        ]

    def _generate_domain_subtasks(self, expert: Dict) -> List[Dict]:
        """Generate domain-specific subtasks."""
        knowledge_context = expert["knowledge_context"]
        questions = knowledge_context["questions_to_ask"]

        subtasks = []
        for i, question in enumerate(questions[:3], 1):  # Limit to 3 questions
            subtasks.append({
                "step": i,
                "action": "domain_query",
                "question": question,
                "knowledge_type": knowledge_context["knowledge_type"],
                "pattern": "llm_query"
            })

        return subtasks

    def _format_user_friendly_response(
        self,
        plan: SwarmExecutionPlan
    ) -> Dict[str, Any]:
        """
        Format the execution plan into a user-friendly response.
        Uses simple language (10-year-old reading level).
        """
        response = {
            "summary": self._create_simple_summary(plan),
            "team": self._explain_the_team(plan.experts),
            "what_will_happen": self._explain_the_process(plan),
            "time_and_cost": self._explain_metrics(plan),
            "questions_we_will_ask": self._extract_questions(plan),
            "artifacts_we_will_create": self._explain_artifacts(plan)
        }

        return response

    def _create_simple_summary(self, plan: SwarmExecutionPlan) -> str:
        """Create a simple summary for the user."""
        expert_count = len(plan.experts)
        complexity_words = {
            "simple": "quick and easy",
            "medium": "pretty standard",
            "complex": "bigger and needs more work"
        }

        return (
            f"I found a great team of {expert_count} expert(s) to help you! "
            f"This looks like a {complexity_words.get(plan.complexity, 'standard')} project. "
            f"Each expert knows special things about different parts of your project."
        )

    def _explain_the_team(self, experts: List[Dict]) -> str:
        """Explain the team to the user in simple terms."""
        explanations = []

        expert_descriptions = {
            "Software Architect": "designs how everything fits together like a puzzle",
            "Frontend Developer": "makes the parts you see and click on",
            "Backend Developer": "makes everything work behind the scenes",
            "Product Designer": "draws what things look like",
            "Project Manager": "keeps everyone on track and organized",
            "Business Analyst": "figures out exactly what you need",
            "Quality Assurance Engineer": "tests everything to make sure it works",
            "Data Scientist": "finds patterns and smart answers in information",
            "DevOps Engineer": "sets everything up so it runs smoothly"
        }

        for expert in experts:
            title = expert["job_title"]
            description = expert_descriptions.get(
                title,
                "helps with an important part of your project"
            )
            explanations.append(f"- **{title}**: {description}")

        return "\n".join(explanations)

    def _explain_the_process(self, plan: SwarmExecutionPlan) -> str:
        """Explain what will happen in simple terms."""
        return (
            "Here's how we'll work together:\n"
            "1. First, we'll ask you some questions to understand what you want\n"
            "2. Then, each expert will look at their part of the project\n"
            "3. We'll break the big project into small, easy pieces\n"
            "4. Each expert will do their special part\n"
            "5. We'll put everything together and check that it works"
        )

    def _explain_metrics(self, plan: SwarmExecutionPlan) -> str:
        """Explain time and cost in simple terms."""
        hours = plan.estimated_metrics["time_hours"]
        cost = plan.estimated_metrics["cost_usd"]
        confidence = plan.estimated_metrics["confidence_score"]

        return (
            f"⏰ **Time**: About {hours} hours of work\n"
            f"💰 **Cost**: Around ${cost}\n"
            f"✅ **Confidence**: {confidence}% sure we can do this well"
        )

    def _extract_questions(self, plan: SwarmExecutionPlan) -> List[str]:
        """Extract questions that experts will ask."""
        questions = []
        for expert in plan.experts:
            for question in expert["knowledge_context"]["questions_to_ask"][:2]:
                questions.append(f"- {expert['job_title']}: {question}")

        return questions[:10]  # Limit to 10 questions

    def _explain_artifacts(self, plan: SwarmExecutionPlan) -> str:
        """Explain what artifacts will be created."""
        artifacts = []
        for artifact in plan.artifacts[:5]:  # Limit to 5 artifacts
            artifacts.append(f"- {artifact['type']} (by {artifact['created_by']})")

        return "We'll create things like:\n" + "\n".join(artifacts)

    def get_expert_details(self, job_title: str) -> Optional[Dict]:
        """Get detailed information about a specific expert."""
        expert = self.swarm.get_expert_by_title(job_title)
        if expert:
            return expert.to_dict()
        return None

    def get_position_details(self, job_title: str) -> Optional[Dict]:
        """Get detailed information about a specific job position."""
        position = self.org_chart.get_position(job_title)
        if position:
            return position.to_dict()
        return None

    def list_available_experts(self) -> List[Dict]:
        """List all available domain experts."""
        return self.swarm.list_all_experts()

    def list_available_positions(self) -> List[Dict]:
        """List all available job positions."""
        return self.org_chart.list_all_positions()

    def get_execution_history(self) -> List[Dict]:
        """Get the history of all executed plans."""
        return [
            {
                "project_description": plan.project_description,
                "complexity": plan.complexity,
                "expert_count": len(plan.experts),
                "estimated_hours": plan.estimated_metrics["time_hours"],
                "estimated_cost": plan.estimated_metrics["cost_usd"]
            }
            for plan in self.execution_history
        ]
