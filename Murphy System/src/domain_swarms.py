"""
Domain-Specific Swarm Generators
Specialized swarms for different problem domains
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from mfgc_core import Phase

logger = logging.getLogger(__name__)


class DomainSwarmGenerator(ABC):
    """Base class for domain-specific swarm generation"""

    def __init__(self, domain_name: str):
        self.domain_name = domain_name

    @abstractmethod
    def generate_candidates(self,
                          task: str,
                          phase: Phase,
                          context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate domain-specific candidates."""
        ...

    @abstractmethod
    def generate_gates(self,
                      candidates: List[Dict[str, Any]],
                      context: Dict[str, Any]) -> List[str]:
        """Generate domain-specific gates."""
        ...


class SoftwareEngineeringSwarm(DomainSwarmGenerator):
    """Swarm generator for software engineering tasks"""

    def __init__(self):
        super().__init__("software_engineering")
        self.architectures = [
            'microservices', 'monolithic', 'serverless',
            'event-driven', 'layered', 'hexagonal'
        ]
        self.tech_stacks = {
            'web': ['React', 'Vue', 'Angular', 'Svelte'],
            'backend': ['Node.js', 'Python/Django', 'Java/Spring', 'Go'],
            'database': ['PostgreSQL', 'MongoDB', 'Redis', 'Cassandra'],
            'cloud': ['AWS', 'GCP', 'Azure', 'DigitalOcean']
        }

    def generate_candidates(self,
                          task: str,
                          phase: Phase,
                          context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate software engineering candidates"""

        if phase == Phase.EXPAND:
            return self._expand_architectures(task, context)
        elif phase == Phase.TYPE:
            return self._type_components(task, context)
        elif phase == Phase.ENUMERATE:
            return self._enumerate_tech_stacks(task, context)
        elif phase == Phase.CONSTRAIN:
            return self._constrain_requirements(task, context)
        elif phase == Phase.COLLAPSE:
            return self._collapse_design(task, context)
        elif phase == Phase.BIND:
            return self._bind_specifications(task, context)
        elif phase == Phase.EXECUTE:
            return self._execute_deployment(task, context)

        return []

    def _expand_architectures(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """EXPAND: Explore different architectures"""
        candidates = []

        for arch in self.architectures:
            candidates.append({
                'type': 'architecture',
                'name': arch,
                'approach': f'{arch.capitalize()} architecture',
                'pros': self._get_architecture_pros(arch),
                'cons': self._get_architecture_cons(arch),
                'score': self._score_architecture(arch, context),
                'requires_validation': ['scalability', 'maintainability', 'cost']
            })

        return candidates

    def _get_architecture_pros(self, arch: str) -> List[str]:
        """Get pros for architecture"""
        pros_map = {
            'microservices': ['Scalable', 'Independent deployment', 'Technology diversity'],
            'monolithic': ['Simple to develop', 'Easy to test', 'Single deployment'],
            'serverless': ['Auto-scaling', 'Pay-per-use', 'No server management'],
            'event-driven': ['Loose coupling', 'Asynchronous', 'Scalable'],
            'layered': ['Clear separation', 'Easy to understand', 'Testable'],
            'hexagonal': ['Highly testable', 'Framework independent', 'Flexible']
        }
        return pros_map.get(arch, ['Flexible', 'Proven'])

    def _get_architecture_cons(self, arch: str) -> List[str]:
        """Get cons for architecture"""
        cons_map = {
            'microservices': ['Complex deployment', 'Network overhead', 'Distributed debugging'],
            'monolithic': ['Hard to scale', 'Tight coupling', 'Long deployment cycles'],
            'serverless': ['Vendor lock-in', 'Cold starts', 'Limited control'],
            'event-driven': ['Complex debugging', 'Eventual consistency', 'Message ordering'],
            'layered': ['Can become rigid', 'Performance overhead', 'Layer violations'],
            'hexagonal': ['Initial complexity', 'More boilerplate', 'Learning curve']
        }
        return cons_map.get(arch, ['Trade-offs exist'])

    def _score_architecture(self, arch: str, context: Dict[str, Any]) -> float:
        """Score architecture based on context"""
        # Simple scoring based on context hints
        score = 0.5

        if 'scalability' in str(context).lower():
            if arch in ['microservices', 'serverless']:
                score += 0.2

        if 'simple' in str(context).lower():
            if arch in ['monolithic', 'layered']:
                score += 0.2

        return min(1.0, score)

    def _type_components(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """TYPE: Categorize components"""
        return [
            {'category': 'frontend', 'technologies': self.tech_stacks['web']},
            {'category': 'backend', 'technologies': self.tech_stacks['backend']},
            {'category': 'database', 'technologies': self.tech_stacks['database']},
            {'category': 'infrastructure', 'technologies': self.tech_stacks['cloud']}
        ]

    def _enumerate_tech_stacks(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """ENUMERATE: List specific tech stacks"""
        stacks = []

        # Generate combinations
        for frontend in self.tech_stacks['web'][:2]:
            for backend in self.tech_stacks['backend'][:2]:
                for db in self.tech_stacks['database'][:2]:
                    stacks.append({
                        'stack': f'{frontend} + {backend} + {db}',
                        'frontend': frontend,
                        'backend': backend,
                        'database': db,
                        'maturity': 'production-ready',
                        'dependencies': [frontend, backend, db]
                    })

        return stacks[:6]  # Limit to 6 combinations

    def _constrain_requirements(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """CONSTRAIN: Apply software engineering constraints"""
        return [
            {'constraint': 'performance', 'requirement': 'Response time < 200ms'},
            {'constraint': 'scalability', 'requirement': 'Handle 10k concurrent users'},
            {'constraint': 'security', 'requirement': 'OWASP Top 10 compliance'},
            {'constraint': 'maintainability', 'requirement': 'Code coverage > 80%'},
            {'constraint': 'availability', 'requirement': '99.9% uptime SLA'}
        ]

    def _collapse_design(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """COLLAPSE: Synthesize final design"""
        return [{
            'solution': 'Hybrid microservices architecture',
            'components': [
                'API Gateway (Node.js)',
                'Auth Service (Python)',
                'Core Service (Go)',
                'Database (PostgreSQL + Redis)',
                'Message Queue (RabbitMQ)'
            ],
            'rationale': 'Balances scalability with maintainability'
        }]

    def _bind_specifications(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """BIND: Create detailed specifications"""
        return [
            {
                'spec_type': 'API Specification',
                'format': 'OpenAPI 3.0',
                'completeness': 0.95,
                'endpoints': 15
            },
            {
                'spec_type': 'Database Schema',
                'format': 'SQL DDL',
                'completeness': 0.90,
                'tables': 12
            },
            {
                'spec_type': 'Deployment Configuration',
                'format': 'Kubernetes YAML',
                'completeness': 0.85,
                'services': 5
            }
        ]

    def _execute_deployment(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """EXECUTE: Deployment steps"""
        return [
            {'step': 'Build Docker images', 'risk': 0.05, 'duration': '5 min'},
            {'step': 'Run integration tests', 'risk': 0.10, 'duration': '10 min'},
            {'step': 'Deploy to staging', 'risk': 0.15, 'duration': '5 min'},
            {'step': 'Run smoke tests', 'risk': 0.10, 'duration': '5 min'},
            {'step': 'Deploy to production', 'risk': 0.25, 'duration': '10 min'},
            {'step': 'Monitor metrics', 'risk': 0.05, 'duration': 'continuous'}
        ]

    def generate_gates(self,
                      candidates: List[Dict[str, Any]],
                      context: Dict[str, Any]) -> List[str]:
        """Generate software engineering gates"""
        gates = [
            "Code review required before merge",
            "All tests must pass (unit, integration, e2e)",
            "Security scan must show no critical vulnerabilities",
            "Performance benchmarks must meet SLA requirements",
            "Database migrations must be reversible",
            "API changes must be backward compatible",
            "Documentation must be updated",
            "Staging deployment must succeed before production",
            "Rollback plan must be documented and tested",
            "Monitoring and alerting must be configured"
        ]

        return gates


class BusinessStrategySwarm(DomainSwarmGenerator):
    """Swarm generator for business strategy tasks"""

    def __init__(self):
        super().__init__("business_strategy")
        self.frameworks = [
            'SWOT', 'Porter Five Forces', 'Blue Ocean',
            'Business Model Canvas', 'Lean Startup', 'OKR'
        ]

    def generate_candidates(self,
                          task: str,
                          phase: Phase,
                          context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate business strategy candidates"""

        if phase == Phase.EXPAND:
            return self._expand_strategies(task, context)
        elif phase == Phase.TYPE:
            return self._type_markets(task, context)
        elif phase == Phase.ENUMERATE:
            return self._enumerate_options(task, context)
        elif phase == Phase.CONSTRAIN:
            return self._constrain_resources(task, context)
        elif phase == Phase.COLLAPSE:
            return self._collapse_strategy(task, context)
        elif phase == Phase.BIND:
            return self._bind_plan(task, context)
        elif phase == Phase.EXECUTE:
            return self._execute_rollout(task, context)

        return []

    def _expand_strategies(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """EXPAND: Explore strategic options"""
        return [
            {
                'strategy': 'Market Penetration',
                'approach': 'Increase market share in existing markets',
                'risk': 0.3,
                'potential_return': 0.6
            },
            {
                'strategy': 'Market Development',
                'approach': 'Enter new markets with existing products',
                'risk': 0.5,
                'potential_return': 0.7
            },
            {
                'strategy': 'Product Development',
                'approach': 'Develop new products for existing markets',
                'risk': 0.6,
                'potential_return': 0.8
            },
            {
                'strategy': 'Diversification',
                'approach': 'New products in new markets',
                'risk': 0.8,
                'potential_return': 0.9
            }
        ]

    def _type_markets(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """TYPE: Categorize markets"""
        return [
            {'market_type': 'B2B', 'characteristics': ['Long sales cycles', 'High value']},
            {'market_type': 'B2C', 'characteristics': ['Short sales cycles', 'Volume']},
            {'market_type': 'B2B2C', 'characteristics': ['Hybrid model', 'Complex']}
        ]

    def _enumerate_options(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """ENUMERATE: List specific options"""
        return [
            {'option': 'Organic growth', 'timeline': '2-3 years', 'investment': 'Low'},
            {'option': 'Strategic partnerships', 'timeline': '1-2 years', 'investment': 'Medium'},
            {'option': 'Acquisition', 'timeline': '6-12 months', 'investment': 'High'}
        ]

    def _constrain_resources(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """CONSTRAIN: Resource constraints"""
        return [
            {'constraint': 'budget', 'limit': '$1M', 'flexibility': 'low'},
            {'constraint': 'timeline', 'limit': '12 months', 'flexibility': 'medium'},
            {'constraint': 'team_size', 'limit': '10 people', 'flexibility': 'high'}
        ]

    def _collapse_strategy(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """COLLAPSE: Final strategy"""
        return [{
            'strategy': 'Phased market development with strategic partnerships',
            'phases': [
                'Phase 1: Validate product-market fit (3 months)',
                'Phase 2: Build partnerships (6 months)',
                'Phase 3: Scale operations (12 months)'
            ],
            'success_metrics': ['Revenue growth', 'Customer acquisition', 'Market share']
        }]

    def _bind_plan(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """BIND: Detailed business plan"""
        return [
            {'document': 'Business Plan', 'pages': 25, 'completeness': 0.90},
            {'document': 'Financial Model', 'scenarios': 3, 'completeness': 0.85},
            {'document': 'Go-to-Market Plan', 'channels': 5, 'completeness': 0.80}
        ]

    def _execute_rollout(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """EXECUTE: Rollout plan"""
        return [
            {'milestone': 'MVP Launch', 'date': 'Month 3', 'risk': 0.3},
            {'milestone': 'First Partnership', 'date': 'Month 6', 'risk': 0.4},
            {'milestone': 'Break-even', 'date': 'Month 12', 'risk': 0.5}
        ]

    def generate_gates(self,
                      candidates: List[Dict[str, Any]],
                      context: Dict[str, Any]) -> List[str]:
        """Generate business strategy gates"""
        return [
            "Market research must validate demand",
            "Financial projections must show positive ROI",
            "Competitive analysis must identify differentiation",
            "Customer interviews must confirm value proposition",
            "Pilot program must meet success criteria",
            "Legal and regulatory compliance must be verified",
            "Risk assessment must identify mitigation strategies",
            "Board approval required for major investments",
            "Key partnerships must be secured before scaling",
            "Exit criteria defined for each phase"
        ]


class ScientificResearchSwarm(DomainSwarmGenerator):
    """Swarm generator for scientific research tasks"""

    def __init__(self):
        super().__init__("scientific_research")
        self.methodologies = [
            'experimental', 'observational', 'computational',
            'theoretical', 'meta-analysis', 'case study'
        ]

    def generate_candidates(self,
                          task: str,
                          phase: Phase,
                          context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate scientific research candidates"""

        if phase == Phase.EXPAND:
            return self._expand_hypotheses(task, context)
        elif phase == Phase.TYPE:
            return self._type_methodologies(task, context)
        elif phase == Phase.ENUMERATE:
            return self._enumerate_experiments(task, context)
        elif phase == Phase.CONSTRAIN:
            return self._constrain_variables(task, context)
        elif phase == Phase.COLLAPSE:
            return self._collapse_findings(task, context)
        elif phase == Phase.BIND:
            return self._bind_paper(task, context)
        elif phase == Phase.EXECUTE:
            return self._execute_publication(task, context)

        return []

    def _expand_hypotheses(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """EXPAND: Generate hypotheses"""
        return [
            {
                'hypothesis': 'H1: Variable X positively correlates with Y',
                'testability': 0.9,
                'novelty': 0.7
            },
            {
                'hypothesis': 'H2: Mechanism M explains phenomenon P',
                'testability': 0.7,
                'novelty': 0.8
            },
            {
                'hypothesis': 'H3: Intervention I improves outcome O',
                'testability': 0.8,
                'novelty': 0.6
            }
        ]

    def _type_methodologies(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """TYPE: Categorize methodologies"""
        return [
            {'methodology': 'Experimental', 'control': 'high', 'cost': 'high'},
            {'methodology': 'Observational', 'control': 'low', 'cost': 'medium'},
            {'methodology': 'Computational', 'control': 'high', 'cost': 'low'}
        ]

    def _enumerate_experiments(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """ENUMERATE: List experiments"""
        return [
            {
                'experiment': 'Pilot study',
                'sample_size': 30,
                'duration': '2 weeks',
                'cost': '$5k'
            },
            {
                'experiment': 'Main study',
                'sample_size': 200,
                'duration': '3 months',
                'cost': '$50k'
            },
            {
                'experiment': 'Replication study',
                'sample_size': 150,
                'duration': '2 months',
                'cost': '$30k'
            }
        ]

    def _constrain_variables(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """CONSTRAIN: Control variables"""
        return [
            {'variable': 'age', 'range': '18-65', 'control': 'stratified'},
            {'variable': 'gender', 'distribution': '50/50', 'control': 'balanced'},
            {'variable': 'location', 'sites': 3, 'control': 'multi-center'}
        ]

    def _collapse_findings(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """COLLAPSE: Synthesize findings"""
        return [{
            'finding': 'Significant positive effect observed (p < 0.05)',
            'effect_size': 0.65,
            'confidence_interval': '95%',
            'implications': 'Supports hypothesis H1'
        }]

    def _bind_paper(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """BIND: Structure paper"""
        return [
            {'section': 'Abstract', 'words': 250, 'completeness': 0.95},
            {'section': 'Introduction', 'words': 1500, 'completeness': 0.90},
            {'section': 'Methods', 'words': 2000, 'completeness': 0.85},
            {'section': 'Results', 'words': 1500, 'completeness': 0.90},
            {'section': 'Discussion', 'words': 2000, 'completeness': 0.85}
        ]

    def _execute_publication(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """EXECUTE: Publication process"""
        return [
            {'step': 'Internal review', 'duration': '2 weeks', 'risk': 0.1},
            {'step': 'Submit to journal', 'duration': '1 week', 'risk': 0.2},
            {'step': 'Peer review', 'duration': '3 months', 'risk': 0.4},
            {'step': 'Revisions', 'duration': '1 month', 'risk': 0.3},
            {'step': 'Acceptance', 'duration': '2 weeks', 'risk': 0.2}
        ]

    def generate_gates(self,
                      candidates: List[Dict[str, Any]],
                      context: Dict[str, Any]) -> List[str]:
        """Generate scientific research gates"""
        return [
            "IRB approval required before human subjects research",
            "Statistical power analysis must justify sample size",
            "Control groups must be properly matched",
            "Blinding procedures must be documented",
            "Data collection protocols must be standardized",
            "Statistical methods must be pre-registered",
            "Raw data must be preserved and documented",
            "Peer review must address all major concerns",
            "Conflicts of interest must be disclosed",
            "Reproducibility materials must be provided"
        ]


class DomainDetector:
    """Detect which domain a task belongs to"""

    def __init__(self):
        self.domain_keywords = {
            'software_engineering': [
                'code', 'software', 'api', 'database', 'deploy',
                'architecture', 'microservices', 'frontend', 'backend',
                'programming', 'development', 'application'
            ],
            'business_strategy': [
                'business', 'strategy', 'market', 'revenue', 'growth',
                'customer', 'partnership', 'investment', 'roi',
                'competitive', 'acquisition', 'expansion'
            ],
            'scientific_research': [
                'research', 'hypothesis', 'experiment', 'study',
                'analysis', 'data', 'statistical', 'methodology',
                'publication', 'peer review', 'findings'
            ]
        }

        self.swarms = {
            'software_engineering': SoftwareEngineeringSwarm(),
            'business_strategy': BusinessStrategySwarm(),
            'scientific_research': ScientificResearchSwarm()
        }

    def detect_domain(self, task: str, context: Dict[str, Any]) -> Optional[str]:
        """Detect domain from task description"""
        task_lower = task.lower()
        context_str = str(context).lower()
        combined = task_lower + ' ' + context_str

        scores = {}
        for domain, keywords in self.domain_keywords.items():
            score = sum(1 for kw in keywords if kw in combined)
            scores[domain] = score

        # Return domain with highest score, or None if no clear match
        max_score = max(scores.values())
        if max_score >= 2:  # At least 2 keyword matches
            return max(scores, key=scores.get)

        return None

    def get_swarm(self, domain: str) -> Optional[DomainSwarmGenerator]:
        """Get swarm generator for domain"""
        return self.swarms.get(domain)
