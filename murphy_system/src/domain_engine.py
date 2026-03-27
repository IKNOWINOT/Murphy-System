"""
Murphy System - Generative Domain Engine
Handles domain classification, generative domain creation, and cross-domain impact analysis
"""

import json
import logging
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("domain_engine")

class DomainType(Enum):
    """Domain type (Enum subclass)."""
    BUSINESS = "business"
    ENGINEERING = "engineering"
    FINANCIAL = "financial"
    LEGAL = "legal"
    OPERATIONS = "operations"
    MARKETING = "marketing"
    HR = "hr"
    SALES = "sales"
    PRODUCT = "product"
    GENERATIVE = "generative"

class ImpactLevel(Enum):
    """Impact level (Enum subclass)."""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3

@dataclass
class DomainImpact:
    """Cross-domain impact definition"""
    target_domain: str
    impact_level: ImpactLevel
    description: str
    dependencies: List[str]
    constraints: List[str]

@dataclass
class Domain:
    """Domain definition"""
    name: str
    domain_type: DomainType
    purpose: str
    sub_domains: List[str]
    key_questions: List[str]
    cross_impacts: Dict[str, DomainImpact]
    constraints: List[str]
    gates: List[str]

    def to_dict(self):
        return {
            'name': self.name,
            'type': self.domain_type.value,
            'purpose': self.purpose,
            'sub_domains': self.sub_domains,
            'key_questions': self.key_questions,
            'cross_impacts': {k: asdict(v) for k, v in self.cross_impacts.items()},
            'constraints': self.constraints,
            'gates': self.gates
        }

@dataclass
class GenerativeDomainTemplate:
    """Template for creating new domains"""
    template_type: str
    name_pattern: str
    discovery_questions: List[str]
    required_fields: List[str]

    def to_dict(self):
        return asdict(self)

class DomainEngine:
    """Main domain classification and generation engine"""

    def __init__(self):
        self.domains = self._initialize_domains()
        self.templates = self._initialize_templates()
        self.generative_domains = {}
        self.cross_impact_matrix = self._build_impact_matrix()

    def _initialize_domains(self) -> Dict[str, Domain]:
        """Initialize all standard domains"""
        domains = {}

        # Business Domain
        domains['business'] = Domain(
            name="Business Domain",
            domain_type=DomainType.BUSINESS,
            purpose="Overarching business strategy and operations",
            sub_domains=[
                "Executive Strategy",
                "Business Development",
                "Market Analysis",
                "Competitive Intelligence",
                "Revenue Models",
                "Growth Planning",
                "Risk Management",
                "Corporate Governance"
            ],
            key_questions=[
                "What is the business model and revenue strategy?",
                "What are the key performance indicators (KPIs)?",
                "What is the competitive landscape?",
                "What are the growth targets and timeline?",
                "What are the critical success factors?",
                "What are the major business risks?",
                "What is the organizational structure?",
                "What are the resource constraints?"
            ],
            cross_impacts={},
            constraints=[
                "Budget limitations",
                "Market conditions",
                "Competitive pressure",
                "Resource availability"
            ],
            gates=[
                "Business Viability Gate",
                "Market Validation Gate",
                "Financial Feasibility Gate",
                "Strategic Alignment Gate"
            ]
        )

        # Engineering Domain
        domains['engineering'] = Domain(
            name="Engineering Domain",
            domain_type=DomainType.ENGINEERING,
            purpose="Technical design, development, and implementation",
            sub_domains=[
                "Software Engineering",
                "Mechanical Engineering",
                "Electrical Engineering",
                "Civil Engineering",
                "Systems Engineering",
                "Quality Engineering",
                "Manufacturing Engineering",
                "Process Engineering"
            ],
            key_questions=[
                "What are the technical requirements and constraints?",
                "What technologies and platforms will be used?",
                "What are the performance requirements?",
                "What are the scalability needs?",
                "What are the integration requirements?",
                "What are the security requirements?",
                "What are the maintenance and support needs?",
                "What are the technical risks?"
            ],
            cross_impacts={},
            constraints=[
                "Technical feasibility",
                "Technology stack limitations",
                "Performance requirements",
                "Integration complexity"
            ],
            gates=[
                "Technical Feasibility Gate",
                "Architecture Review Gate",
                "Security Review Gate",
                "Performance Validation Gate",
                "Integration Testing Gate"
            ]
        )

        # Financial Domain
        domains['financial'] = Domain(
            name="Financial Domain",
            domain_type=DomainType.FINANCIAL,
            purpose="Financial planning, analysis, and management",
            sub_domains=[
                "Accounting",
                "Financial Planning & Analysis (FP&A)",
                "Treasury Management",
                "Tax Planning",
                "Investment Analysis",
                "Cost Accounting",
                "Budgeting",
                "Financial Reporting"
            ],
            key_questions=[
                "What is the total budget and cost structure?",
                "What are the revenue projections?",
                "What is the cash flow timeline?",
                "What are the funding requirements?",
                "What are the financial risks?",
                "What are the tax implications?",
                "What are the financial reporting requirements?",
                "What is the ROI and payback period?"
            ],
            cross_impacts={},
            constraints=[
                "Budget constraints",
                "Cash flow limitations",
                "ROI requirements",
                "Financial reporting standards"
            ],
            gates=[
                "Budget Approval Gate",
                "Financial Viability Gate",
                "ROI Validation Gate",
                "Cost Control Gate"
            ]
        )

        # Legal Domain
        domains['legal'] = Domain(
            name="Legal Domain",
            domain_type=DomainType.LEGAL,
            purpose="Legal compliance, risk management, and protection",
            sub_domains=[
                "Corporate Law",
                "Contract Law",
                "Intellectual Property",
                "Regulatory Compliance",
                "Employment Law",
                "Tax Law",
                "Litigation",
                "Privacy & Data Protection"
            ],
            key_questions=[
                "What are the regulatory requirements?",
                "What are the compliance obligations?",
                "What are the contractual requirements?",
                "What are the IP considerations?",
                "What are the liability risks?",
                "What are the privacy requirements?",
                "What are the employment law considerations?",
                "What are the dispute resolution mechanisms?"
            ],
            cross_impacts={},
            constraints=[
                "Regulatory compliance",
                "Legal liability",
                "Contractual obligations",
                "IP protection requirements"
            ],
            gates=[
                "Legal Review Gate",
                "Compliance Validation Gate",
                "Contract Review Gate",
                "IP Protection Gate"
            ]
        )

        # Operations Domain
        domains['operations'] = Domain(
            name="Operations Domain",
            domain_type=DomainType.OPERATIONS,
            purpose="Day-to-day execution and process management",
            sub_domains=[
                "Supply Chain Management",
                "Logistics",
                "Quality Control",
                "Process Optimization",
                "Facilities Management",
                "Vendor Management",
                "Inventory Management",
                "Customer Service"
            ],
            key_questions=[
                "What are the operational processes?",
                "What are the capacity requirements?",
                "What are the quality standards?",
                "What are the supply chain requirements?",
                "What are the logistics needs?",
                "What are the vendor relationships?",
                "What are the operational risks?",
                "What are the efficiency targets?"
            ],
            cross_impacts={},
            constraints=[
                "Operational capacity",
                "Process efficiency",
                "Quality standards",
                "Resource availability"
            ],
            gates=[
                "Operational Readiness Gate",
                "Quality Assurance Gate",
                "Process Validation Gate",
                "Capacity Planning Gate"
            ]
        )

        # Marketing Domain
        domains['marketing'] = Domain(
            name="Marketing Domain",
            domain_type=DomainType.MARKETING,
            purpose="Market positioning, brand building, and customer acquisition",
            sub_domains=[
                "Brand Strategy",
                "Content Marketing",
                "Digital Marketing",
                "Product Marketing",
                "Market Research",
                "Public Relations",
                "Advertising",
                "Customer Analytics"
            ],
            key_questions=[
                "Who is the target audience?",
                "What is the value proposition?",
                "What are the marketing channels?",
                "What is the brand positioning?",
                "What is the competitive differentiation?",
                "What is the marketing budget?",
                "What are the success metrics?",
                "What is the go-to-market strategy?"
            ],
            cross_impacts={},
            constraints=[
                "Marketing budget",
                "Brand guidelines",
                "Market conditions",
                "Competitive landscape"
            ],
            gates=[
                "Brand Alignment Gate",
                "Market Validation Gate",
                "Campaign Approval Gate",
                "ROI Validation Gate"
            ]
        )

        # HR Domain
        domains['hr'] = Domain(
            name="Human Resources Domain",
            domain_type=DomainType.HR,
            purpose="Talent management and organizational development",
            sub_domains=[
                "Recruitment",
                "Training & Development",
                "Compensation & Benefits",
                "Performance Management",
                "Employee Relations",
                "Organizational Development",
                "HR Compliance",
                "Workforce Planning"
            ],
            key_questions=[
                "What are the staffing requirements?",
                "What are the skill requirements?",
                "What is the organizational structure?",
                "What is the compensation strategy?",
                "What are the training needs?",
                "What is the company culture?",
                "What are the retention strategies?",
                "What are the HR compliance requirements?"
            ],
            cross_impacts={},
            constraints=[
                "Talent availability",
                "Compensation budget",
                "Employment regulations",
                "Cultural fit"
            ],
            gates=[
                "Staffing Approval Gate",
                "Compensation Review Gate",
                "Compliance Validation Gate",
                "Culture Fit Gate"
            ]
        )

        # Sales Domain
        domains['sales'] = Domain(
            name="Sales Domain",
            domain_type=DomainType.SALES,
            purpose="Revenue generation and customer relationships",
            sub_domains=[
                "Sales Strategy",
                "Account Management",
                "Sales Operations",
                "Channel Management",
                "Sales Enablement",
                "Customer Success",
                "Pricing Strategy",
                "Contract Negotiation"
            ],
            key_questions=[
                "What is the sales strategy?",
                "Who are the target customers?",
                "What is the sales process?",
                "What are the sales channels?",
                "What is the pricing strategy?",
                "What are the sales targets?",
                "What is the customer acquisition cost?",
                "What is the sales cycle length?"
            ],
            cross_impacts={},
            constraints=[
                "Sales targets",
                "Pricing constraints",
                "Channel limitations",
                "Customer expectations"
            ],
            gates=[
                "Sales Readiness Gate",
                "Pricing Approval Gate",
                "Contract Review Gate",
                "Customer Validation Gate"
            ]
        )

        # Product Domain
        domains['product'] = Domain(
            name="Product Domain",
            domain_type=DomainType.PRODUCT,
            purpose="Product strategy, development, and management",
            sub_domains=[
                "Product Strategy",
                "Product Development",
                "Product Design",
                "User Experience (UX)",
                "Product Analytics",
                "Product Marketing",
                "Product Operations",
                "Roadmap Planning"
            ],
            key_questions=[
                "What problem does the product solve?",
                "Who is the target user?",
                "What are the key features?",
                "What is the product roadmap?",
                "What is the competitive landscape?",
                "What are the success metrics?",
                "What is the pricing strategy?",
                "What is the go-to-market plan?"
            ],
            cross_impacts={},
            constraints=[
                "Product-market fit",
                "Development resources",
                "Time to market",
                "Competitive pressure"
            ],
            gates=[
                "Product-Market Fit Gate",
                "Feature Validation Gate",
                "UX Review Gate",
                "Launch Readiness Gate"
            ]
        )

        return domains

    def _build_impact_matrix(self) -> Dict[str, Dict[str, ImpactLevel]]:
        """Build cross-domain impact matrix"""
        matrix = {
            'business': {
                'engineering': ImpactLevel.HIGH,
                'financial': ImpactLevel.HIGH,
                'legal': ImpactLevel.MEDIUM,
                'operations': ImpactLevel.HIGH,
                'marketing': ImpactLevel.HIGH,
                'hr': ImpactLevel.MEDIUM,
                'sales': ImpactLevel.HIGH,
                'product': ImpactLevel.HIGH
            },
            'engineering': {
                'business': ImpactLevel.HIGH,
                'financial': ImpactLevel.MEDIUM,
                'legal': ImpactLevel.MEDIUM,
                'operations': ImpactLevel.HIGH,
                'marketing': ImpactLevel.LOW,
                'hr': ImpactLevel.LOW,
                'sales': ImpactLevel.LOW,
                'product': ImpactLevel.HIGH
            },
            'financial': {
                'business': ImpactLevel.HIGH,
                'engineering': ImpactLevel.MEDIUM,
                'legal': ImpactLevel.HIGH,
                'operations': ImpactLevel.MEDIUM,
                'marketing': ImpactLevel.MEDIUM,
                'hr': ImpactLevel.MEDIUM,
                'sales': ImpactLevel.MEDIUM,
                'product': ImpactLevel.MEDIUM
            },
            'legal': {
                'business': ImpactLevel.MEDIUM,
                'engineering': ImpactLevel.MEDIUM,
                'financial': ImpactLevel.HIGH,
                'operations': ImpactLevel.MEDIUM,
                'marketing': ImpactLevel.MEDIUM,
                'hr': ImpactLevel.HIGH,
                'sales': ImpactLevel.MEDIUM,
                'product': ImpactLevel.MEDIUM
            },
            'operations': {
                'business': ImpactLevel.HIGH,
                'engineering': ImpactLevel.HIGH,
                'financial': ImpactLevel.MEDIUM,
                'legal': ImpactLevel.MEDIUM,
                'marketing': ImpactLevel.LOW,
                'hr': ImpactLevel.MEDIUM,
                'sales': ImpactLevel.MEDIUM,
                'product': ImpactLevel.MEDIUM
            },
            'marketing': {
                'business': ImpactLevel.HIGH,
                'engineering': ImpactLevel.LOW,
                'financial': ImpactLevel.MEDIUM,
                'legal': ImpactLevel.MEDIUM,
                'operations': ImpactLevel.LOW,
                'hr': ImpactLevel.LOW,
                'sales': ImpactLevel.HIGH,
                'product': ImpactLevel.HIGH
            },
            'hr': {
                'business': ImpactLevel.MEDIUM,
                'engineering': ImpactLevel.LOW,
                'financial': ImpactLevel.MEDIUM,
                'legal': ImpactLevel.HIGH,
                'operations': ImpactLevel.MEDIUM,
                'marketing': ImpactLevel.LOW,
                'sales': ImpactLevel.MEDIUM,
                'product': ImpactLevel.MEDIUM
            },
            'sales': {
                'business': ImpactLevel.HIGH,
                'engineering': ImpactLevel.LOW,
                'financial': ImpactLevel.MEDIUM,
                'legal': ImpactLevel.MEDIUM,
                'operations': ImpactLevel.MEDIUM,
                'marketing': ImpactLevel.HIGH,
                'hr': ImpactLevel.MEDIUM,
                'product': ImpactLevel.HIGH
            },
            'product': {
                'business': ImpactLevel.HIGH,
                'engineering': ImpactLevel.HIGH,
                'financial': ImpactLevel.MEDIUM,
                'legal': ImpactLevel.MEDIUM,
                'operations': ImpactLevel.MEDIUM,
                'marketing': ImpactLevel.HIGH,
                'hr': ImpactLevel.MEDIUM,
                'sales': ImpactLevel.HIGH
            }
        }
        return matrix

    def _initialize_templates(self) -> Dict[str, GenerativeDomainTemplate]:
        """Initialize generative domain templates"""
        templates = {}

        # New Industry Vertical Template
        templates['industry'] = GenerativeDomainTemplate(
            template_type="industry",
            name_pattern="{industry} Domain",
            discovery_questions=[
                "What are the unique characteristics of this industry?",
                "What are the regulatory requirements specific to this industry?",
                "What are the standard practices in this industry?",
                "What are the key success factors?",
                "What are the common challenges?",
                "What are the industry-specific metrics?",
                "What are the competitive dynamics?",
                "What are the technology requirements?"
            ],
            required_fields=[
                "industry_name",
                "regulatory_requirements",
                "standard_practices",
                "success_factors"
            ]
        )

        # Hybrid Domain Template
        templates['hybrid'] = GenerativeDomainTemplate(
            template_type="hybrid",
            name_pattern="{domain_a} + {domain_b} Hybrid",
            discovery_questions=[
                "How do these domains interact?",
                "What are the integration points?",
                "What are the conflicting requirements?",
                "What are the synergies?",
                "What are the unique challenges of combining these?",
                "What expertise is required?",
                "What are the success criteria?",
                "What are the risks of integration?"
            ],
            required_fields=[
                "primary_domain_a",
                "primary_domain_b",
                "integration_points",
                "synergies"
            ]
        )

        # Emerging Technology Template
        templates['technology'] = GenerativeDomainTemplate(
            template_type="technology",
            name_pattern="{technology} Domain",
            discovery_questions=[
                "What problem does this technology solve?",
                "What are the technical requirements?",
                "What is the maturity level of this technology?",
                "What are the implementation challenges?",
                "What expertise is required?",
                "What are the costs and ROI?",
                "What are the risks?",
                "What are the competitive advantages?"
            ],
            required_fields=[
                "technology_name",
                "problem_solved",
                "maturity_level",
                "implementation_challenges"
            ]
        )

        # Process Innovation Template
        templates['process'] = GenerativeDomainTemplate(
            template_type="process",
            name_pattern="{process} Innovation Domain",
            discovery_questions=[
                "What is the current state?",
                "What is the desired future state?",
                "What is the innovation?",
                "What are the benefits?",
                "What are the risks?",
                "What are the implementation requirements?",
                "What are the success metrics?",
                "What are the change management needs?"
            ],
            required_fields=[
                "process_name",
                "current_state",
                "future_state",
                "innovation_description"
            ]
        )

        return templates

    def analyze_request(self, request: str) -> Dict:
        """Analyze request and determine domain coverage"""
        # Extract keywords
        keywords = self._extract_keywords(request.lower())

        # Match against existing domains
        domain_matches = {}
        for domain_name, domain in self.domains.items():
            score = self._calculate_domain_match(keywords, domain)
            if score > 0:
                domain_matches[domain_name] = score

        # Calculate coverage
        total_score = sum(domain_matches.values())
        coverage = min(total_score / 10.0, 1.0)  # Normalize to 0-1

        return {
            'coverage': coverage,
            'matched_domains': domain_matches,
            'needs_generative': coverage < 0.7,
            'keywords': keywords
        }

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from text"""
        # Simple keyword extraction (can be enhanced with NLP)
        domain_keywords = {
            'business': ['business', 'strategy', 'revenue', 'growth', 'market', 'competitive'],
            'engineering': ['technical', 'engineering', 'development', 'architecture', 'system', 'software'],
            'financial': ['financial', 'budget', 'cost', 'roi', 'investment', 'accounting'],
            'legal': ['legal', 'compliance', 'regulatory', 'contract', 'liability', 'ip'],
            'operations': ['operations', 'process', 'logistics', 'supply chain', 'quality'],
            'marketing': ['marketing', 'brand', 'advertising', 'campaign', 'customer'],
            'hr': ['hr', 'hiring', 'talent', 'employee', 'training', 'compensation'],
            'sales': ['sales', 'revenue', 'customer', 'pricing', 'channel', 'account'],
            'product': ['product', 'feature', 'roadmap', 'user', 'design', 'ux']
        }

        found_keywords = []
        for domain, keywords in domain_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    found_keywords.append(keyword)

        return found_keywords

    def _calculate_domain_match(self, keywords: List[str], domain: Domain) -> float:
        """Calculate how well keywords match a domain"""
        score = 0.0
        domain_text = f"{domain.name} {domain.purpose} {' '.join(domain.sub_domains)}".lower()

        for keyword in keywords:
            if keyword in domain_text:
                score += 1.0

        return score

    def select_template(self, request: str, analysis: Dict) -> GenerativeDomainTemplate:
        """Select appropriate template for generative domain"""
        keywords = analysis['keywords']

        # Check for industry-specific terms
        industry_terms = ['healthcare', 'finance', 'retail', 'manufacturing', 'education']
        if any(term in request.lower() for term in industry_terms):
            return self.templates['industry']

        # Check for multiple domain mentions
        if len(analysis['matched_domains']) >= 2:
            return self.templates['hybrid']

        # Check for technology terms
        tech_terms = ['ai', 'ml', 'blockchain', 'iot', 'cloud', 'automation']
        if any(term in request.lower() for term in tech_terms):
            return self.templates['technology']

        # Default to process innovation
        return self.templates['process']

    def generate_questions(self, template: GenerativeDomainTemplate, request: str) -> List[Dict]:
        """Generate questions for domain discovery"""
        questions = []

        # Add template questions
        for i, question in enumerate(template.discovery_questions):
            questions.append({
                'id': f'q{i+1}',
                'question': question,
                'type': 'text',
                'required': True
            })

        # Add cross-domain impact questions
        for domain_name in self.domains.keys():
            questions.append({
                'id': f'impact_{domain_name}',
                'question': f'How does this affect {domain_name}?',
                'type': 'text',
                'required': False
            })

        return questions

    def synthesize_domain(self, template: GenerativeDomainTemplate,
                         responses: Dict) -> Domain:
        """Create new domain from template and responses"""
        # Extract domain name
        if template.template_type == 'industry':
            domain_name = responses.get('industry_name', 'Custom') + ' Domain'
        elif template.template_type == 'hybrid':
            domain_a = responses.get('primary_domain_a', 'Domain A')
            domain_b = responses.get('primary_domain_b', 'Domain B')
            domain_name = f"{domain_a} + {domain_b} Hybrid"
        elif template.template_type == 'technology':
            domain_name = responses.get('technology_name', 'Technology') + ' Domain'
        else:
            domain_name = responses.get('process_name', 'Process') + ' Innovation Domain'

        # Extract purpose
        purpose = responses.get('purpose', 'Custom domain for specific requirements')

        # Extract sub-domains
        sub_domains = responses.get('sub_domains', [])
        if isinstance(sub_domains, str):
            sub_domains = [s.strip() for s in sub_domains.split(',')]

        # Extract constraints
        constraints = responses.get('constraints', [])
        if isinstance(constraints, str):
            constraints = [c.strip() for c in constraints.split(',')]

        # Generate gates
        gates = self._generate_domain_gates(domain_name, responses)

        # Build cross-impacts
        cross_impacts = {}
        for domain_name_key in self.domains.keys():
            impact_key = f'impact_{domain_name_key}'
            if impact_key in responses and responses[impact_key]:
                cross_impacts[domain_name_key] = DomainImpact(
                    target_domain=domain_name_key,
                    impact_level=ImpactLevel.MEDIUM,  # Default, can be refined
                    description=responses[impact_key],
                    dependencies=[],
                    constraints=[]
                )

        # Create domain
        domain = Domain(
            name=domain_name,
            domain_type=DomainType.GENERATIVE,
            purpose=purpose,
            sub_domains=sub_domains,
            key_questions=template.discovery_questions,
            cross_impacts=cross_impacts,
            constraints=constraints,
            gates=gates
        )

        return domain

    def _generate_domain_gates(self, domain_name: str, responses: Dict) -> List[str]:
        """Generate validation gates for domain"""
        gates = [
            f"{domain_name} Feasibility Gate",
            f"{domain_name} Requirements Gate",
            f"{domain_name} Validation Gate",
            f"{domain_name} Compliance Gate"
        ]

        # Add custom gates based on responses
        if 'regulatory_requirements' in responses:
            gates.append(f"{domain_name} Regulatory Gate")

        if 'quality_standards' in responses:
            gates.append(f"{domain_name} Quality Gate")

        return gates

    def validate_domain(self, domain: Domain) -> Tuple[bool, List[str]]:
        """Validate domain completeness"""
        issues = []

        if not domain.name:
            issues.append("Domain name is required")

        if not domain.purpose:
            issues.append("Domain purpose is required")

        if len(domain.sub_domains) == 0:
            issues.append("At least one sub-domain is required")

        if len(domain.key_questions) == 0:
            issues.append("Key questions are required")

        if len(domain.gates) == 0:
            issues.append("At least one gate is required")

        return len(issues) == 0, issues

    def integrate_domain(self, domain: Domain) -> bool:
        """Integrate new domain into system"""
        # Add to generative domains
        domain_key = domain.name.lower().replace(' ', '_')
        self.generative_domains[domain_key] = domain

        # Update cross-impact matrix
        self._update_impact_matrix(domain)

        return True

    def _update_impact_matrix(self, domain: Domain):
        """Update cross-impact matrix with new domain"""
        domain_key = domain.name.lower().replace(' ', '_')

        # Add row for new domain
        self.cross_impact_matrix[domain_key] = {}

        # Add impacts from new domain to existing domains
        for target_domain, impact in domain.cross_impacts.items():
            self.cross_impact_matrix[domain_key][target_domain] = impact.impact_level

        # Add impacts from existing domains to new domain (default to MEDIUM)
        for existing_domain in self.domains.keys():
            if existing_domain not in self.cross_impact_matrix:
                self.cross_impact_matrix[existing_domain] = {}
            self.cross_impact_matrix[existing_domain][domain_key] = ImpactLevel.MEDIUM

    def get_all_domains(self) -> List[Dict]:
        """Get all domains (standard + generative)"""
        all_domains = []

        for domain in self.domains.values():
            all_domains.append(domain.to_dict())

        for domain in self.generative_domains.values():
            all_domains.append(domain.to_dict())

        return all_domains

    def get_cross_impact_analysis(self, domain_names: List[str]) -> Dict:
        """Get cross-domain impact analysis"""
        analysis = {
            'domains': domain_names,
            'impacts': {},
            'high_impact_pairs': [],
            'dependencies': []
        }

        for source in domain_names:
            analysis['impacts'][source] = {}
            for target in domain_names:
                if source != target and source in self.cross_impact_matrix:
                    impact = self.cross_impact_matrix[source].get(target, ImpactLevel.NONE)
                    analysis['impacts'][source][target] = impact.value

                    if impact == ImpactLevel.HIGH:
                        analysis['high_impact_pairs'].append({
                            'source': source,
                            'target': target,
                            'level': 'HIGH'
                        })

        return analysis

# Example usage
if __name__ == "__main__":
    engine = DomainEngine()

    # Test request analysis
    request = "Build an AI-powered sustainable supply chain system"
    analysis = engine.analyze_request(request)
    logger.info(f"Analysis: {analysis}")

    # Test template selection
    if analysis['needs_generative']:
        template = engine.select_template(request, analysis)
        logger.info(f"Selected template: {template.template_type}")

        # Generate questions
        questions = engine.generate_questions(template, request)
        logger.info(f"Generated {len(questions)} questions")
