"""
Inquisitory Choice Engine
Uses deductive reasoning and statistical knowledge of organization operations
Provides choice recommendations and decision support
"""

import json
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("inquisitory_engine")


class ChoiceType(Enum):
    """Types of choices/recommendations"""
    TECHNICAL = "technical"
    ARCHITECTURAL = "architectural"
    RESOURCE = "resource"
    PROCESS = "process"
    STRATEGIC = "strategic"


class ChoiceConfidence(Enum):
    """Confidence levels for choices"""
    HIGH = "high"  # > 0.9
    MEDIUM = "medium"  # 0.7-0.9
    LOW = "low"  # 0.5-0.7
    UNCERTAIN = "uncertain"  # < 0.5


@dataclass
class ChoiceOption:
    """A specific choice option"""
    option_id: str
    name: str
    description: str
    pros: List[str]
    cons: List[str]
    estimated_cost: float
    estimated_time: int  # in hours
    risk_level: str  # low, medium, high
    success_probability: float
    dependencies: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "option_id": self.option_id,
            "name": self.name,
            "description": self.description,
            "pros": self.pros,
            "cons": self.cons,
            "estimated_cost": self.estimated_cost,
            "estimated_time": self.estimated_time,
            "risk_level": self.risk_level,
            "success_probability": self.success_probability,
            "dependencies": self.dependencies,
            "required_capabilities": self.required_capabilities
        }


@dataclass
class ChoiceRecommendation:
    """A choice recommendation with scoring"""
    recommendation_id: str
    choice_type: ChoiceType
    question: str
    options: List[ChoiceOption]
    recommended_option: str  # option_id
    confidence: ChoiceConfidence
    confidence_score: float
    reasoning: str
    context: Dict[str, Any]
    statistical_basis: Dict[str, Any]
    created_at: str

    def to_dict(self) -> Dict:
        return {
            "recommendation_id": self.recommendation_id,
            "choice_type": self.choice_type.value,
            "question": self.question,
            "options": [o.to_dict() for o in self.options],
            "recommended_option": self.recommended_option,
            "confidence": self.confidence.value,
            "confidence_score": self.confidence_score,
            "reasoning": self.reasoning,
            "context": self.context,
            "statistical_basis": self.statistical_basis,
            "created_at": self.created_at
        }


@dataclass
class DecisionTree:
    """Decision tree for complex choices"""
    tree_id: str
    name: str
    root_node: str
    nodes: Dict[str, Dict[str, Any]]

    def to_dict(self) -> Dict:
        return {
            "tree_id": self.tree_id,
            "name": self.name,
            "root_node": self.root_node,
            "nodes": self.nodes
        }


class InquisitoryEngine:
    """
    Inquisitory choice engine using deductive reasoning
    Provides recommendations based on statistical knowledge of organizations
    """

    def __init__(self):
        self.recommendation_count = 0
        self.decision_trees = self._load_decision_trees()
        self.statistical_knowledge = self._load_statistical_knowledge()
        self.organization_patterns = self._load_organization_patterns()

    def _load_decision_trees(self) -> Dict[str, DecisionTree]:
        """Load decision trees for common scenarios"""
        return {
            "tech_stack_selection": DecisionTree(
                tree_id="tech_stack_selection",
                name="Technology Stack Selection",
                root_node="question_1",
                nodes={
                    "question_1": {
                        "question": "What is the primary type of application?",
                        "options": {
                            "web": "question_2",
                            "mobile": "question_3",
                            "api": "question_4",
                            "data_processing": "question_5"
                        }
                    },
                    "question_2": {
                        "question": "What is the expected scale?",
                        "options": {
                            "small": "recommend_react_django",
                            "medium": "recommend_react_node",
                            "large": "recommend_react_microservices"
                        }
                    },
                    "question_3": {
                        "question": "Platform preference?",
                        "options": {
                            "ios": "recommend_swift",
                            "android": "recommend_kotlin",
                            "cross_platform": "recommend_react_native"
                        }
                    },
                    "question_4": {
                        "question": "Data requirements?",
                        "options": {
                            "simple": "recommend_node_express",
                            "complex": "recommend_python_fastapi",
                            "high_performance": "recommend_go"
                        }
                    },
                    "question_5": {
                        "question": "Processing type?",
                        "options": {
                            "batch": "recommend_python_pandas",
                            "streaming": "recommend_apache_kafka",
                            "ml": "recommend_python_tensorflow"
                        }
                    },
                    "recommend_react_django": {
                        "type": "recommendation",
                        "technology": "React + Django",
                        "justification": "Simple to set up, great documentation, suitable for small web apps"
                    },
                    "recommend_react_node": {
                        "type": "recommendation",
                        "technology": "React + Node.js",
                        "justification": "JavaScript everywhere, large ecosystem, good for medium scale"
                    },
                    "recommend_react_microservices": {
                        "type": "recommendation",
                        "technology": "React + Microservices (Node/Go/Python)",
                        "justification": "Scalable, fault-tolerant, suitable for large scale"
                    }
                }
            ),
            "cloud_provider_selection": DecisionTree(
                tree_id="cloud_provider_selection",
                name="Cloud Provider Selection",
                root_node="question_1",
                nodes={
                    "question_1": {
                        "question": "What is your primary concern?",
                        "options": {
                            "cost": "question_2",
                            "features": "question_3",
                            "ecosystem": "question_4"
                        }
                    },
                    "question_2": {
                        "question": "What is your scale?",
                        "options": {
                            "startup": "recommend_gcp",
                            "enterprise": "recommend_aws",
                            "microsoft_stack": "recommend_azure"
                        }
                    },
                    "question_3": {
                        "question": "What features do you need?",
                        "options": {
                            "ml_ai": "recommend_gcp",
                            "analytics": "recommend_azure",
                            "broad_services": "recommend_aws"
                        }
                    },
                    "question_4": {
                        "question": "Existing infrastructure?",
                        "options": {
                            "none": "recommend_aws",
                            "microsoft": "recommend_azure",
                            "google": "recommend_gcp"
                        }
                    },
                    "recommend_aws": {
                        "type": "recommendation",
                        "provider": "AWS",
                        "justification": "Market leader, most comprehensive services, large ecosystem"
                    },
                    "recommend_gcp": {
                        "type": "recommendation",
                        "provider": "Google Cloud Platform",
                        "justification": "Best for ML/AI, innovative features, cost-effective for startups"
                    },
                    "recommend_azure": {
                        "type": "recommendation",
                        "provider": "Microsoft Azure",
                        "justification": "Great for enterprises, integrates with Microsoft stack, strong analytics"
                    }
                }
            )
        }

    def _load_statistical_knowledge(self) -> Dict[str, Any]:
        """Load statistical knowledge about organizations"""
        return {
            "tech_stack_success_rates": {
                "react_django": {"success_rate": 0.85, "avg_completion_time": 160, "sample_size": 500},
                "react_node": {"success_rate": 0.88, "avg_completion_time": 150, "sample_size": 750},
                "react_microservices": {"success_rate": 0.75, "avg_completion_time": 240, "sample_size": 300},
                "python_fastapi": {"success_rate": 0.90, "avg_completion_time": 140, "sample_size": 400},
                "go_api": {"success_rate": 0.92, "avg_completion_time": 130, "sample_size": 250}
            },
            "cloud_provider_adoption": {
                "aws": {"market_share": 0.32, "satisfaction_score": 8.5},
                "azure": {"market_share": 0.21, "satisfaction_score": 8.3},
                "gcp": {"market_share": 0.10, "satisfaction_score": 8.7},
                "other": {"market_share": 0.37, "satisfaction_score": 8.0}
            },
            "project_completion_by_team_size": {
                "1_2": {"completion_rate": 0.70, "avg_time": 180},
                "3_5": {"completion_rate": 0.85, "avg_time": 140},
                "6_10": {"completion_rate": 0.90, "avg_time": 120},
                "10+": {"completion_rate": 0.80, "avg_time": 130}
            },
            "risk_factors": {
                "new_technology": {"failure_risk_increase": 0.15},
                "tight_deadline": {"failure_risk_increase": 0.20},
                "complex_requirements": {"failure_risk_increase": 0.10},
                "limited_budget": {"failure_risk_increase": 0.12}
            }
        }

    def _load_organization_patterns(self) -> Dict[str, Any]:
        """Load patterns of how organizations typically operate"""
        return {
            "startup_patterns": {
                "typical_team_size": [2, 5],
                "common_tech_stack": ["react", "node", "python", "postgreSQL"],
                "common_cloud_providers": ["aws", "gcp"],
                "development_approach": ["agile", "mvp"],
                "decision_factors": ["speed_to_market", "cost", "scalability"]
            },
            "enterprise_patterns": {
                "typical_team_size": [10, 50],
                "common_tech_stack": ["java", ".net", "react", "oracle"],
                "common_cloud_providers": ["aws", "azure"],
                "development_approach": ["waterfall", "hybrid"],
                "decision_factors": ["compliance", "security", "stability"]
            },
            "agency_patterns": {
                "typical_team_size": [5, 15],
                "common_tech_stack": ["react", "vue", "node", "python"],
                "common_cloud_providers": ["aws", "digitalocean"],
                "development_approach": ["agile", "iterative"],
                "decision_factors": ["client_budget", "timeline", "quality"]
            }
        }

    def analyze_choice(
        self,
        question: str,
        choice_type: ChoiceType,
        options: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> ChoiceRecommendation:
        """
        Analyze a choice and provide recommendation

        Args:
            question: The question or decision to make
            choice_type: Type of choice
            options: List of option dictionaries
            context: Additional context (budget, timeline, constraints, etc.)

        Returns:
            ChoiceRecommendation object
        """
        self.recommendation_count += 1
        recommendation_id = f"rec_{self.recommendation_count}"

        # Create ChoiceOption objects
        choice_options = []
        for i, opt in enumerate(options):
            option = ChoiceOption(
                option_id=f"opt_{i}",
                name=opt.get("name", f"Option {i+1}"),
                description=opt.get("description", ""),
                pros=opt.get("pros", []),
                cons=opt.get("cons", []),
                estimated_cost=opt.get("estimated_cost", 0),
                estimated_time=opt.get("estimated_time", 0),
                risk_level=opt.get("risk_level", "medium"),
                success_probability=opt.get("success_probability", 0.7),
                dependencies=opt.get("dependencies", []),
                required_capabilities=opt.get("required_capabilities", [])
            )
            choice_options.append(option)

        # Score each option
        scores = {}
        for option in choice_options:
            scores[option.option_id] = self._score_option(
                option, choice_type, context
            )

        # Select recommended option
        recommended_option_id = max(scores, key=scores.get)
        confidence_score = scores[recommended_option_id]

        # Determine confidence level
        if confidence_score > 0.9:
            confidence = ChoiceConfidence.HIGH
        elif confidence_score > 0.7:
            confidence = ChoiceConfidence.MEDIUM
        elif confidence_score > 0.5:
            confidence = ChoiceConfidence.LOW
        else:
            confidence = ChoiceConfidence.UNCERTAIN

        # Generate reasoning
        reasoning = self._generate_reasoning(
            recommended_option_id, choice_options, scores, context
        )

        # Get statistical basis
        statistical_basis = self._get_statistical_basis(choice_type, recommended_option_id)

        # Create recommendation
        recommendation = ChoiceRecommendation(
            recommendation_id=recommendation_id,
            choice_type=choice_type,
            question=question,
            options=choice_options,
            recommended_option=recommended_option_id,
            confidence=confidence,
            confidence_score=confidence_score,
            reasoning=reasoning,
            context=context or {},
            statistical_basis=statistical_basis,
            created_at=datetime.now(timezone.utc).isoformat()
        )

        return recommendation

    def _score_option(
        self,
        option: ChoiceOption,
        choice_type: ChoiceType,
        context: Optional[Dict[str, Any]]
    ) -> float:
        """Score an option based on multiple factors"""
        score = 0.0

        # Base score from success probability
        score += option.success_probability * 0.4

        # Cost score (lower is better)
        budget = context.get("budget", float('inf')) if context else float('inf')
        if budget > 0:
            if option.estimated_cost <= budget:
                cost_score = 1.0 - (option.estimated_cost / budget) * 0.5
                score += cost_score * 0.2
            else:
                score -= 0.2  # Penalty for over budget

        # Time score (lower is better)
        timeline = context.get("timeline", float('inf')) if context else float('inf')
        if timeline > 0:
            if option.estimated_time <= timeline:
                time_score = 1.0 - (option.estimated_time / timeline) * 0.5
                score += time_score * 0.15
            else:
                score -= 0.15  # Penalty for over timeline

        # Risk score
        risk_scores = {"low": 0.1, "medium": 0.0, "high": -0.1}
        score += risk_scores.get(option.risk_level, 0.0) * 0.15

        # Statistical knowledge
        stats = self._get_statistical_score(option, choice_type)
        score += stats * 0.1

        # Cap score at 1.0
        return min(1.0, max(0.0, score))

    def _get_statistical_score(
        self,
        option: ChoiceOption,
        choice_type: ChoiceType
    ) -> float:
        """Get statistical score for option"""
        # Simplified - in production would use actual statistical models
        if choice_type == ChoiceType.TECHNICAL:
            # Check if option matches successful patterns
            tech_stack_success = self.statistical_knowledge.get("tech_stack_success_rates", {})
            for tech_key, data in tech_stack_success.items():
                if tech_key in option.name.lower():
                    return data.get("success_rate", 0.7)

        return 0.75  # Default average

    def _generate_reasoning(
        self,
        recommended_id: str,
        options: List[ChoiceOption],
        scores: Dict[str, float],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Generate reasoning for recommendation"""
        recommended = next((o for o in options if o.option_id == recommended_id), None)
        if not recommended:
            return "Unable to generate reasoning"

        reasoning_parts = [f"Recommended: {recommended.name}"]
        reasoning_parts.append(f"Score: {scores[recommended_id]:.2f}")

        # Add context-based reasoning
        if context:
            if "budget" in context:
                if recommended.estimated_cost <= context["budget"]:
                    reasoning_parts.append("Fits within budget")
                else:
                    reasoning_parts.append("Slightly exceeds budget but offers best value")

            if "timeline" in context:
                if recommended.estimated_time <= context["timeline"]:
                    reasoning_parts.append("Meets timeline requirements")

        # Add pros emphasis
        if recommended.pros:
            reasoning_parts.append(f"Key benefits: {', '.join(recommended.pros[:2])}")

        # Add statistical backing
        stats = self._get_statistical_basis(None, recommended_id)
        if stats:
            reasoning_parts.append(f"Based on statistical data: {stats.get('description', '')}")

        return ". ".join(reasoning_parts)

    def _get_statistical_basis(
        self,
        choice_type: Optional[ChoiceType],
        option_id: str
    ) -> Dict[str, Any]:
        """Get statistical basis for recommendation"""
        # Simplified - in production would provide detailed statistics
        return {
            "source": "historical_organization_data",
            "sample_size": 1000,
            "confidence_interval": 0.95,
            "description": "Based on analysis of similar organizations and projects"
        }

    def navigate_decision_tree(
        self,
        tree_id: str,
        answers: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Navigate a decision tree with given answers

        Args:
            tree_id: ID of decision tree to use
            answers: Dictionary of question IDs to answers

        Returns:
            Recommendation node or None if path incomplete
        """
        if tree_id not in self.decision_trees:
            return None

        tree = self.decision_trees[tree_id]
        current_node = tree.root_node

        while current_node in tree.nodes:
            node = tree.nodes[current_node]

            if node.get("type") == "recommendation":
                return node

            if current_node not in answers:
                return None  # Incomplete path

            answer = answers[current_node]
            if answer not in node.get("options", {}):
                return None  # Invalid answer

            current_node = node["options"][answer]

        return None

    def get_next_question(
        self,
        tree_id: str,
        answers: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Get the next question in a decision tree

        Args:
            tree_id: ID of decision tree
            answers: Answers provided so far

        Returns:
            Next question node or None if complete
        """
        result = self.navigate_decision_tree(tree_id, answers)

        if result and result.get("type") == "recommendation":
            return result  # Complete, return recommendation

        if result is None:
            # Navigate to find where we are
            if tree_id not in self.decision_trees:
                return None

            tree = self.decision_trees[tree_id]
            current_node = tree.root_node

            while current_node in tree.nodes:
                if current_node not in answers:
                    # Return this question
                    return tree.nodes[current_node]

                node = tree.nodes[current_node]
                if node.get("type") == "recommendation":
                    return node

                answer = answers[current_node]
                if answer not in node.get("options", {}):
                    return None

                current_node = node["options"][answer]

        return None

    def deductive_reasoning(
        self,
        premises: List[str],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply deductive reasoning to premises

        Args:
            premises: List of factual premises
            context: Additional context

        Returns:
            Reasoning result with conclusion
        """
        # Simplified deductive reasoning
        conclusions = []
        confidence = 0.0

        # Pattern matching on premises
        for premise in premises:
            premise_lower = premise.lower()

            # Budget constraints
            if "budget" in premise_lower and ("limited" in premise_lower or "small" in premise_lower):
                conclusions.append("Recommend cost-effective solutions")
                conclusions.append("Prioritize open-source technologies")
                confidence += 0.2

            # Time constraints
            if "deadline" in premise_lower and ("tight" in premise_lower or "short" in premise_lower):
                conclusions.append("Recommend proven, stable technologies")
                conclusions.append("Avoid experimental frameworks")
                confidence += 0.2

            # Scale requirements
            if "scale" in premise_lower and ("large" in premise_lower or "millions" in premise_lower):
                conclusions.append("Recommend scalable architecture")
                conclusions.append("Consider microservices")
                confidence += 0.2

            # Security requirements
            if "security" in premise_lower or "compliance" in premise_lower:
                conclusions.append("Prioritize security-first approach")
                conclusions.append("Ensure compliance standards")
                confidence += 0.2

        # Normalize confidence
        confidence = min(1.0, confidence / (len(premises) or 1) if premises else 0.0)

        return {
            "premises": premises,
            "conclusions": conclusions,
            "confidence": confidence,
            "reasoning_method": "deductive_pattern_matching"
        }

    def generate_choice_report(
        self,
        recommendations: List[ChoiceRecommendation]
    ) -> Dict[str, Any]:
        """
        Generate comprehensive choice report

        Args:
            recommendations: List of recommendations to include

        Returns:
            Report dictionary
        """
        # Count by type
        by_type = {}
        for rec in recommendations:
            rec_type = rec.choice_type.value
            by_type[rec_type] = by_type.get(rec_type, 0) + 1

        # Count by confidence
        by_confidence = {}
        for rec in recommendations:
            conf = rec.confidence.value
            by_confidence[conf] = by_confidence.get(conf, 0) + 1

        # Calculate average confidence
        avg_confidence = sum(r.confidence_score for r in recommendations) / (len(recommendations) or 1) if recommendations else 0.0

        return {
            "total_recommendations": len(recommendations),
            "by_type": by_type,
            "by_confidence": by_confidence,
            "average_confidence": avg_confidence,
            "high_confidence_count": sum(1 for r in recommendations if r.confidence == ChoiceConfidence.HIGH),
            "recommendations": [r.to_dict() for r in recommendations]
        }


if __name__ == "__main__":
    # Test inquisitory engine
    engine = InquisitoryEngine()

    # Test 1: Analyze tech stack choice
    logger.info("=== Test 1: Analyze Tech Stack Choice ===")
    question = "Which technology stack should we use for our web application?"
    options = [
        {
            "name": "React + Django",
            "description": "React frontend with Django backend",
            "pros": ["Simple setup", "Good documentation", "Rapid development"],
            "cons": ["Limited scalability", "Python performance"],
            "estimated_cost": 5000,
            "estimated_time": 160,
            "risk_level": "low",
            "success_probability": 0.85
        },
        {
            "name": "React + Node.js",
            "description": "Full JavaScript stack",
            "pros": ["Large ecosystem", "Good performance", "Consistent language"],
            "cons": ["Async complexity", "NPM issues"],
            "estimated_cost": 6000,
            "estimated_time": 150,
            "risk_level": "medium",
            "success_probability": 0.88
        },
        {
            "name": "React + Microservices",
            "description": "Scalable microservices architecture",
            "pros": ["Highly scalable", "Fault-tolerant", "Flexible"],
            "cons": ["Complex setup", "Operational overhead"],
            "estimated_cost": 15000,
            "estimated_time": 240,
            "risk_level": "high",
            "success_probability": 0.75
        }
    ]

    context = {
        "budget": 10000,
        "timeline": 200,
        "team_size": 4
    }

    recommendation = engine.analyze_choice(
        question=question,
        choice_type=ChoiceType.TECHNICAL,
        options=options,
        context=context
    )

    logger.info(f"Question: {recommendation.question}")
    logger.info(f"Recommended: {recommendation.options[0].name if recommendation.options else 'N/A'}")
    logger.info(f"Confidence: {recommendation.confidence.value} ({recommendation.confidence_score:.2f})")
    logger.info(f"Reasoning: {recommendation.reasoning}")

    # Test 2: Navigate decision tree
    logger.info("\n=== Test 2: Navigate Decision Tree ===")
    answers = {
        "question_1": "web",
        "question_2": "medium"
    }

    result = engine.navigate_decision_tree("tech_stack_selection", answers)
    if result:
        logger.info(f"Recommendation: {result.get('technology')}")
        logger.info(f"Justification: {result.get('justification')}")

    # Test 3: Get next question
    logger.info("\n=== Test 3: Get Next Question ===")
    next_question = engine.get_next_question("tech_stack_selection", {"question_1": "web"})
    if next_question and next_question.get("question"):
        logger.info(f"Question: {next_question['question']}")
        logger.info(f"Options: {list(next_question.get('options', {}).keys())}")

    # Test 4: Deductive reasoning
    logger.info("\n=== Test 4: Deductive Reasoning ===")
    premises = [
        "The project has a tight deadline",
        "The budget is limited",
        "Security is a high priority",
        "We need to scale to millions of users"
    ]

    result = engine.deductive_reasoning(premises, {})
    logger.info("Conclusions:")
    for conclusion in result["conclusions"]:
        logger.info(f"  - {conclusion}")
    logger.info(f"Confidence: {result['confidence']:.2f}")

    # Test 5: Generate report
    logger.info("\n=== Test 5: Generate Report ===")
    report = engine.generate_choice_report([recommendation])
    logger.info(f"Total Recommendations: {report['total_recommendations']}")
    logger.info(f"Average Confidence: {report['average_confidence']:.2f}")
    logger.info(f"High Confidence: {report['high_confidence_count']}")
