# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Enhanced Librarian System for Complete Business Automation

This system extends the original librarian to support:
- Discovery question flows
- Domain-based gate generation
- Business practice database
- Document intake and analysis
- Org chart generation
- Best practices enforcement
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DiscoveryPhase(Enum):
    """Phases of the discovery process"""
    INITIAL = "initial"
    BUSINESS_TYPE = "business_type"
    ORG_CHART = "org_chart"
    DOCUMENTS = "documents"
    DOMAIN_ANALYSIS = "domain_analysis"
    GATE_GENERATION = "gate_generation"
    WORKFLOW_CREATION = "workflow_creation"
    COMPLETE = "complete"


@dataclass
class DiscoveryQuestion:
    """A single question in the discovery flow"""
    question: str
    question_type: str  # text, select, multiselect, file
    options: List[str] = field(default_factory=list)
    depends_on: Optional[str] = None  # Previous answer that triggers this
    domain: Optional[str] = None  # Domain this question relates to
    is_required: bool = True


@dataclass
class BusinessDomain:
    """A business domain with its practices and metrics"""
    name: str
    description: str
    best_practices: List[str]
    typical_roles: List[str]
    key_metrics: List[str]
    required_gates: List[str]
    example_commands: List[str]


@dataclass
class OrgRole:
    """A role in the organization chart"""
    title: str
    department: str
    level: str  # executive, management, individual
    responsibilities: List[str]
    domain: str
    reports_to: Optional[str] = None
    commands: List[str] = field(default_factory=list)


@dataclass
class GeneratedGate:
    """A gate generated from business practices"""
    name: str
    domain: str
    description: str
    input_requirements: List[str]
    output_requirements: List[str]
    validation_criteria: List[str]
    success_metrics: List[str]
    connected_bots: List[str]


@dataclass
class BotWorkflow:
    """A workflow executed by bots"""
    name: str
    description: str
    trigger: str
    bot_sequence: List[str]  # Ordered list of bot names
    handoffs: List[Dict[str, str]]  # Who hands off to whom
    commands: List[str]  # Hybrid commands (comma-separated with # comments)
    success_criteria: List[str]


class BusinessPracticeDatabase:
    """Database of business practices across domains"""
    
    def __init__(self):
        self.domains: Dict[str, BusinessDomain] = {}
        self._initialize_domains()
    
    def _initialize_domains(self):
        """Initialize standard business domains"""
        
        # Software Company Domain
        self.domains["software_company"] = BusinessDomain(
            name="software_company",
            description="Software development and SaaS business",
            best_practices=[
                "Agile development methodology",
                "CI/CD pipeline implementation",
                "Code review processes",
                "Security by design",
                "User-centered design",
                "Data-driven decision making",
                "Customer feedback loops",
                "Scalable architecture planning"
            ],
            typical_roles=[
                "CEO", "CTO", "CFO", "VP Engineering",
                "VP Product", "VP Sales", "VP Marketing",
                "Software Engineer", "QA Engineer",
                "DevOps Engineer", "Product Manager"
            ],
            key_metrics=[
                "MRR (Monthly Recurring Revenue)",
                "Churn Rate",
                "Customer Acquisition Cost",
                "Customer Lifetime Value",
                "NPS Score",
                "Deployment Frequency",
                "Lead Time for Changes",
                "Mean Time to Recovery"
            ],
            required_gates=[
                "Technical Architecture Review",
                "Security Compliance Gate",
                "Performance Benchmark Gate",
                "User Acceptance Testing Gate",
                "Financial Approval Gate"
            ],
            example_commands=[
                "/swarm generate SeniorEngineer #implement user authentication system",
                "/analyze code #review security vulnerabilities",
                "/deploy production #version 2.1.0"
            ]
        )
        
        # Marketing Domain
        self.domains["marketing"] = BusinessDomain(
            name="marketing",
            description="Marketing and customer acquisition",
            best_practices=[
                "Multi-channel marketing strategy",
                "Content marketing calendar",
                "SEO optimization",
                "Social media engagement",
                "Email marketing automation",
                "Marketing attribution tracking",
                "A/B testing protocols",
                "Brand consistency guidelines"
            ],
            typical_roles=[
                "VP Marketing", "Content Manager",
                "SEO Specialist", "Social Media Manager",
                "Email Marketing Specialist", "Marketing Analyst"
            ],
            key_metrics=[
                "Conversion Rate",
                "Cost Per Lead",
                "Return on Ad Spend",
                "Email Open Rate",
                "Social Engagement Rate",
                "Content Performance Score"
            ],
            required_gates=[
                "Campaign Approval Gate",
                "Brand Compliance Gate",
                "Budget Allocation Gate",
                "Content Quality Gate",
                "ROI Validation Gate"
            ],
            example_commands=[
                "/campaign launch #Q4 product launch",
                "/content create #blog post about AI automation",
                "/analyze metrics #last 30 days performance"
            ]
        )
        
        # Sales Domain
        self.domains["sales"] = BusinessDomain(
            name="sales",
            description="Sales and revenue generation",
            best_practices=[
                "Structured sales process",
                "Lead scoring system",
                "CRM data integrity",
                "Value-based selling",
                "Proposal automation",
                "Contract workflow management",
                "Sales forecasting",
                "Customer relationship nurturing"
            ],
            typical_roles=[
                "VP Sales", "Sales Director",
                "Account Executive", "Sales Engineer",
                "Sales Operations Manager", "Customer Success Manager"
            ],
            key_metrics=[
                "Deal Velocity",
                "Win Rate",
                "Average Deal Size",
                "Sales Pipeline Coverage",
                "Quota Attainment",
                "Customer Retention Rate"
            ],
            required_gates=[
                "Lead Qualification Gate",
                "Proposal Approval Gate",
                "Pricing Authority Gate",
                "Contract Review Gate",
                "Revenue Recognition Gate"
            ],
            example_commands=[
                "/lead qualify #enterprise prospect",
                "/proposal generate #SaaS platform deal",
                "/contract review #master services agreement"
            ]
        )
        
        # Finance Domain
        self.domains["finance"] = BusinessDomain(
            name="finance",
            description="Financial management and operations",
            best_practices=[
                "GAAP compliance",
                "Budget planning and tracking",
                "Cash flow management",
                "Financial forecasting",
                "Audit trail maintenance",
                "Tax compliance",
                "Cost control measures",
                "Financial reporting automation"
            ],
            typical_roles=[
                "CFO", "Controller", "Financial Analyst",
                "Accountant", "Tax Specialist", "FP&A Manager"
            ],
            key_metrics=[
                "Gross Margin",
                "Operating Margin",
                "EBITDA",
                "Cash Burn Rate",
                "Runway",
                "Accounts Receivable Turnover"
            ],
            required_gates=[
                "Budget Approval Gate",
                "Expense Review Gate",
                "Revenue Recognition Gate",
                "Financial Reporting Gate",
                "Compliance Audit Gate"
            ],
            example_commands=[
                "/budget create #Q4 2025",
                "/forecast revenue #12 month projection",
                "/report financial #monthly P&L"
            ]
        )
    
    def get_domain(self, domain_name: str) -> Optional[BusinessDomain]:
        """Get a domain by name"""
        return self.domains.get(domain_name)
    
    def get_all_domains(self) -> List[BusinessDomain]:
        """Get all domains"""
        return list(self.domains.values())
    
    def search_domains(self, query: str) -> List[BusinessDomain]:
        """Search domains by query"""
        query = query.lower()
        results = []
        for domain in self.domains.values():
            if (query in domain.name.lower() or
                query in domain.description.lower() or
                any(query in practice.lower() for practice in domain.best_practices)):
                results.append(domain)
        return results


class EnhancedLibrarianSystem:
    """
    Enhanced Librarian for Complete Business Automation
    
    This system guides users through discovering their business needs,
    generates appropriate gates, creates org charts, and builds
    automated bot workflows.
    """
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.practice_db = BusinessPracticeDatabase()
        self.discovery_phase = DiscoveryPhase.INITIAL
        self.discovery_answers: Dict[str, Any] = {}
        self.generated_org_chart: List[OrgRole] = []
        self.generated_gates: List[GeneratedGate] = []
        self.generated_workflows: List[BotWorkflow] = []
        
        logger.info("Enhanced Librarian System initialized")
    
    def ask(self, user_input: str) -> Dict[str, Any]:
        """
        Process user input and return appropriate response
        
        This is the main entry point for natural language interaction
        """
        user_input = user_input.strip()
        
        # Handle special commands
        if user_input.startswith("/librarian "):
            return self._handle_librarian_command(user_input[10:])
        
        # Otherwise, process based on current discovery phase
        if self.discovery_phase == DiscoveryPhase.INITIAL:
            return self._handle_initial_input(user_input)
        elif self.discovery_phase == DiscoveryPhase.COMPLETE:
            return self._handle_system_running(user_input)
        else:
            return self._handle_discovery_answer(user_input)
    
    def _handle_librarian_command(self, command: str) -> Dict[str, Any]:
        """Handle explicit /librarian commands"""
        parts = command.split(maxsplit=1)
        action = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""
        
        if action == "start" or action == "begin":
            return self.start_discovery()
        
        elif action == "help":
            return self._get_librarian_help()
        
        elif action == "interpret" or action == "explain":
            return self.interpret_command(args)
        
        elif action == "status":
            return self.get_discovery_status()
        
        elif action == "generate":
            return self.generate_system(args)
        
        elif action == "natural":
            return self.command_to_natural(args)
        
        else:
            return self._unknown_librarian_command(action)
    
    def start_discovery(self) -> Dict[str, Any]:
        """Start the discovery process"""
        self.discovery_phase = DiscoveryPhase.BUSINESS_TYPE
        self.discovery_answers = {}
        
        return {
            "type": "question",
            "phase": "business_type",
            "question": "Welcome to the Murphy System Business Automation Setup. To create your complete automated system, I need to understand your business.",
            "follow_up": "What type of business are you?",
            "options": [
                "Software / SaaS Company",
                "Marketing Agency",
                "Consulting Firm",
                "E-commerce",
                "Manufacturing",
                "Other (describe)"
            ],
            "librarian_response": "L: To generate your complete business automation system, I'll need to collect some information about your business."
        }
    
    def _handle_initial_input(self, user_input: str) -> Dict[str, Any]:
        """Handle initial user input"""
        if any(keyword in user_input.lower() for keyword in 
               ["automate", "setup", "create system", "generate", "start"]):
            return self.start_discovery()
        else:
            return {
                "type": "suggestion",
                "message": "I'm ready to help you set up complete business automation.",
                "suggestion": "Type '/librarian start' to begin the discovery process, or describe what you'd like to automate."
            }
    
    def _handle_discovery_answer(self, user_input: str) -> Dict[str, Any]:
        """Handle answers during discovery phase"""
        
        if self.discovery_phase == DiscoveryPhase.BUSINESS_TYPE:
            return self._process_business_type(user_input)
        
        elif self.discovery_phase == DiscoveryPhase.ORG_CHART:
            return self._process_org_chart(user_input)
        
        elif self.discovery_phase == DiscoveryPhase.DOCUMENTS:
            return self._process_documents(user_input)
        
        elif self.discovery_phase == DiscoveryPhase.DOMAIN_ANALYSIS:
            return self._process_domain_analysis(user_input)
        
        elif self.discovery_phase == DiscoveryPhase.GATE_GENERATION:
            return self._process_gate_generation(user_input)
        
        elif self.discovery_phase == DiscoveryPhase.WORKFLOW_CREATION:
            return self._process_workflow_creation(user_input)
        
        return self._unknown_discovery_phase()
    
    def _process_business_type(self, user_input: str) -> Dict[str, Any]:
        """Process business type answer"""
        self.discovery_answers["business_type"] = user_input
        
        # Determine primary domains
        if "software" in user_input.lower() or "saas" in user_input.lower():
            self.discovery_answers["domains"] = ["software_company", "sales", "marketing", "finance"]
        elif "marketing" in user_input.lower():
            self.discovery_answers["domains"] = ["marketing", "sales", "finance"]
        elif "consulting" in user_input.lower():
            self.discovery_answers["domains"] = ["software_company", "sales", "finance"]
        elif "ecommerce" in user_input.lower() or "e-commerce" in user_input.lower():
            self.discovery_answers["domains"] = ["sales", "marketing", "finance"]
        else:
            self.discovery_answers["domains"] = ["software_company", "sales", "marketing", "finance"]
        
        self.discovery_phase = DiscoveryPhase.ORG_CHART
        
        return {
            "type": "question",
            "phase": "org_chart",
            "question": f"Excellent! A {user_input}. Now I need to understand your organization structure.",
            "follow_up": "What is your current team size and structure? (e.g., '10 people: CEO, 3 engineers, 2 sales, 1 marketing, 1 finance')",
            "librarian_response": f"L: For a {user_input}, we'll need to map out your organization to assign the right bots and automation.",
            "hint": "This helps me generate the appropriate executive bots and their handoffs."
        }
    
    def _process_org_chart(self, user_input: str) -> Dict[str, Any]:
        """Process org chart information"""
        self.discovery_answers["org_structure"] = user_input
        
        # Generate org chart based on input
        self._generate_org_chart_from_input(user_input)
        
        self.discovery_phase = DiscoveryPhase.DOCUMENTS
        
        org_summary = ", ".join([role.title for role in self.generated_org_chart[:5]])
        if len(self.generated_org_chart) > 5:
            org_summary += f", and {len(self.generated_org_chart) - 5} more roles"
        
        return {
            "type": "info",
            "phase": "org_chart_generated",
            "message": "I've generated an organization chart for your business.",
            "org_chart": [role.__dict__ for role in self.generated_org_chart],
            "follow_up": "Do you have any existing business documents I should analyze? (business plan, SOPs, process docs)",
            "options": [
                "Yes, upload documents",
                "No, generate from scratch",
                "Skip for now"
            ],
            "librarian_response": f"L: I've identified key roles: {org_summary}. Each will have domain-specific bots.",
            "hint": "Documents help me understand your existing processes and terminology."
        }
    
    def _generate_org_chart_from_input(self, user_input: str) -> None:
        """Generate org chart from user input"""
        domains = self.discovery_answers.get("domains", [])
        self.generated_org_chart = []
        
        # Always start with executives
        self.generated_org_chart.append(OrgRole(
            title="CEO",
            department="Executive",
            level="executive",
            responsibilities=["Business strategy", "Company vision", "Executive decisions"],
            domain="executive",
            commands=["/plan strategy #quarterly business objectives"]
        ))
        
        self.generated_org_chart.append(OrgRole(
            title="CTO",
            department="Technology",
            level="executive",
            responsibilities=["Technical strategy", "Architecture decisions", "Technology stack"],
            domain="technology",
            reports_to="CEO",
            commands=["/plan architecture #system design", "/review technical #decisions"]
        ))
        
        self.generated_org_chart.append(OrgRole(
            title="CFO",
            department="Finance",
            level="executive",
            responsibilities=["Financial planning", "Budget management", "Financial reporting"],
            domain="finance",
            reports_to="CEO",
            commands=["/budget plan #annual financial plan", "/report financial #monthly metrics"]
        ))
        
        # Add domain-specific roles based on business type
        if "software_company" in domains:
            self.generated_org_chart.append(OrgRole(
                title="VP Engineering",
                department="Engineering",
                level="management",
                responsibilities=["Engineering team", "Development process", "Technical delivery"],
                domain="engineering",
                reports_to="CTO",
                commands=["/swarm generate EngineeringTeam #implement features", "/review code #pull requests"]
            ))
            
            self.generated_org_chart.append(OrgRole(
                title="VP Product",
                department="Product",
                level="management",
                responsibilities=["Product strategy", "Feature roadmap", "User experience"],
                domain="product",
                reports_to="CEO",
                commands=["/plan roadmap #product features", "/analyze user #feedback and requirements"]
            ))
        
        if "marketing" in domains:
            self.generated_org_chart.append(OrgRole(
                title="VP Marketing",
                department="Marketing",
                level="management",
                responsibilities=["Marketing strategy", "Campaign execution", "Brand management"],
                domain="marketing",
                reports_to="CEO",
                commands=["/campaign launch #marketing initiative", "/analyze metrics #campaign performance"]
            ))
            
            self.generated_org_chart.append(OrgRole(
                title="Content Manager",
                department="Marketing",
                level="individual",
                responsibilities=["Content creation", "Content calendar", "SEO optimization"],
                domain="marketing",
                reports_to="VP Marketing",
                commands=["/content create #marketing materials", "/optimize seo #web content"]
            ))
        
        if "sales" in domains:
            self.generated_org_chart.append(OrgRole(
                title="VP Sales",
                department="Sales",
                level="management",
                responsibilities=["Sales strategy", "Revenue targets", "Sales team"],
                domain="sales",
                reports_to="CEO",
                commands=["/forecast sales #quarterly targets", "/analyze pipeline #deal progression"]
            ))
            
            self.generated_org_chart.append(OrgRole(
                title="Account Executive",
                department="Sales",
                level="individual",
                responsibilities=["Lead qualification", "Deal closing", "Client relationships"],
                domain="sales",
                reports_to="VP Sales",
                commands=["/lead qualify #prospects", "/proposal generate #client solutions"]
            ))
    
    def _process_documents(self, user_input: str) -> Dict[str, Any]:
        """Process document upload decision"""
        self.discovery_answers["has_documents"] = "yes" in user_input.lower()
        
        if "yes" in user_input.lower():
            self.discovery_phase = DiscoveryPhase.DOMAIN_ANALYSIS
            return {
                "type": "question",
                "phase": "document_upload",
                "question": "Great! Please upload your documents.",
                "follow_up": "Upload your business plan, SOPs, or any process documents.",
                "librarian_response": "L: I'll analyze your documents to understand your existing processes and terminology.",
                "hint": "This helps tailor the automation to your specific business practices.",
                "file_upload_enabled": True
            }
        else:
            # Skip documents and go to domain analysis
            return self._process_domain_analysis("Skip documents")
    
    def _process_domain_analysis(self, user_input: str) -> Dict[str, Any]:
        """Process domain analysis"""
        self.discovery_answers["domain_analysis_complete"] = True
        self.discovery_phase = DiscoveryPhase.GATE_GENERATION
        
        domains = self.discovery_answers.get("domains", [])
        
        # Generate gates for each domain
        self._generate_gates_for_domains(domains)
        
        gate_summary = f"{len(self.generated_gates)} quality gates across {len(domains)} domains"
        
        return {
            "type": "info",
            "phase": "gates_generated",
            "message": f"I've generated {gate_summary} based on best practices.",
            "gates": [gate.__dict__ for gate in self.generated_gates],
            "follow_up": "Should I create the automated bot workflows now?",
            "options": [
                "Yes, create workflows",
                "Review gates first",
                "Add custom gates"
            ],
            "librarian_response": f"L: Generated {gate_summary}. Each gate enforces best practices for that domain.",
            "hint": "Gates ensure quality and compliance in all automated processes."
        }
    
    def _generate_gates_for_domains(self, domains: List[str]) -> None:
        """Generate gates for each domain"""
        self.generated_gates = []
        
        for domain_name in domains:
            domain = self.practice_db.get_domain(domain_name)
            if domain:
                for gate_name in domain.required_gates:
                    gate = GeneratedGate(
                        name=gate_name,
                        domain=domain_name,
                        description=f"Quality gate for {gate_name} in {domain.name}",
                        input_requirements=self._generate_gate_inputs(domain_name, gate_name),
                        output_requirements=self._generate_gate_outputs(domain_name, gate_name),
                        validation_criteria=self._generate_validation_criteria(domain_name, gate_name),
                        success_metrics=domain.key_metrics[:3],
                        connected_bots=[role.title for role in self.generated_org_chart 
                                      if role.domain == domain_name or role.domain == "executive"]
                    )
                    self.generated_gates.append(gate)
    
    def _generate_gate_inputs(self, domain: str, gate: str) -> List[str]:
        """Generate input requirements for a gate"""
        return [
            f"{domain} documentation",
            f"Review criteria for {gate}",
            "Stakeholder approvals",
            "Compliance checklist"
        ]
    
    def _generate_gate_outputs(self, domain: str, gate: str) -> List[str]:
        """Generate output requirements for a gate"""
        return [
            f"{gate} approval",
            "Quality assessment report",
            "Action items if any",
            "Next step recommendations"
        ]
    
    def _generate_validation_criteria(self, domain: str, gate: str) -> List[str]:
        """Generate validation criteria for a gate"""
        return [
            f"Meets {domain} best practices",
            "Stakeholder sign-off obtained",
            "Compliance requirements met",
            "Quality standards satisfied"
        ]
    
    def _process_gate_generation(self, user_input: str) -> Dict[str, Any]:
        """Process gate generation decision"""
        if "review" in user_input.lower():
            return {
                "type": "info",
                "message": "Here are all generated gates:",
                "gates": [gate.__dict__ for gate in self.generated_gates],
                "follow_up": "Ready to create workflows?"
            }
        
        elif "custom" in user_input.lower():
            self.discovery_phase = DiscoveryPhase.WORKFLOW_CREATION
            return {
                "type": "question",
                "phase": "custom_gates",
                "question": "What custom gates would you like to add?",
                "follow_up": "Describe the gate name, domain, and requirements.",
                "librarian_response": "L: Custom gates allow you to enforce your specific business requirements."
            }
        
        else:  # Yes, create workflows
            return self._process_workflow_creation("Create workflows")
    
    def _process_workflow_creation(self, user_input: str) -> Dict[str, Any]:
        """Process workflow creation"""
        self.discovery_answers["workflows_created"] = True
        self.discovery_phase = DiscoveryPhase.COMPLETE
        
        # Generate bot workflows
        self._generate_bot_workflows()
        
        # Generate command examples
        command_examples = self._generate_hybrid_command_examples()
        
        return {
            "type": "system_ready",
            "message": "Your complete business automation system is ready!",
            "phase": "complete",
            "org_chart": [role.__dict__ for role in self.generated_org_chart],
            "gates": [gate.__dict__ for gate in self.generated_gates],
            "workflows": [workflow.__dict__ for workflow in self.generated_workflows],
            "command_examples": command_examples,
            "librarian_response": "L: Your system is now ready! You have automated bots for each role, connected through workflows, with quality gates enforcing best practices.",
            "follow_up": "Try commands like:\n" + "\n".join(command_examples[:3]),
            "hint": "Use /librarian interpret <command> to understand any command in natural language."
        }
    
    def _generate_bot_workflows(self) -> None:
        """Generate bot workflows"""
        self.generated_workflows = []
        
        # Executive Planning Workflow
        self.generated_workflows.append(BotWorkflow(
            name="Executive Planning",
            description="Quarterly business planning executed by executive bots",
            trigger="/plan strategy #quarterly objectives",
            bot_sequence=["CEO", "CTO", "CFO"],
            handoffs=[
                {"from": "CEO", "to": "CTO", "context": "Business objectives and vision"},
                {"from": "CTO", "to": "CFO", "context": "Technical requirements and budget"},
                {"from": "CFO", "to": "CEO", "context": "Financial approval and constraints"}
            ],
            commands=[
                "/plan strategy #quarterly business objectives, /plan architecture #technical roadmap, /budget plan #resource allocation, /approve executive #final plan"
            ],
            success_criteria=[
                "All executive approvals obtained",
                "Financial plan approved",
                "Technical roadmap defined",
                "Stakeholders aligned"
            ]
        ))
        
        # Sales Pipeline Workflow
        self.generated_workflows.append(BotWorkflow(
            name="Sales Pipeline",
            description="Lead to closed deal automation",
            trigger="/lead qualify #prospect",
            bot_sequence=["Account Executive", "VP Sales", "CFO"],
            handoffs=[
                {"from": "Account Executive", "to": "VP Sales", "context": "Qualified prospect and proposal"},
                {"from": "VP Sales", "to": "CFO", "context": "Deal terms and pricing"},
                {"from": "CFO", "to": "Account Executive", "context": "Approved contract"}
            ],
            commands=[
                "/lead qualify #enterprise prospect, /proposal generate #custom solution, /review pricing #deal terms, /contract create #master agreement, /approve sales #final deal"
            ],
            success_criteria=[
                "Lead qualified according to criteria",
                "Proposal meets requirements",
                "Pricing within approved ranges",
                "Contract signed"
            ]
        ))
        
        # Marketing Campaign Workflow
        if "marketing" in self.discovery_answers.get("domains", []):
            self.generated_workflows.append(BotWorkflow(
                name="Marketing Campaign",
                description="Campaign planning and execution",
                trigger="/campaign launch #new initiative",
                bot_sequence=["VP Marketing", "Content Manager", "CFO"],
                handoffs=[
                    {"from": "VP Marketing", "to": "Content Manager", "context": "Campaign brief and strategy"},
                    {"from": "Content Manager", "to": "VP Marketing", "context": "Content assets and materials"},
                    {"from": "VP Marketing", "to": "CFO", "context": "Campaign budget and ROI projection"},
                    {"from": "CFO", "to": "VP Marketing", "context": "Budget approval"}
                ],
                commands=[
                    "/campaign plan #Q4 launch, /content create #marketing materials, /analyze metrics #target audience, /budget allocate #campaign spend, /approve marketing #go live"
                ],
                success_criteria=[
                    "Campaign aligned with strategy",
                    "Content meets brand guidelines",
                    "Budget approved",
                    "ROI targets defined"
                ]
            ))
        
        # Software Development Workflow
        if "software_company" in self.discovery_answers.get("domains", []):
            self.generated_workflows.append(BotWorkflow(
                name="Software Development",
                description="Feature development and deployment",
                trigger="/swarm generate EngineeringTeam #implement feature",
                bot_sequence=["VP Engineering", "Software Engineer", "QA Engineer", "CTO"],
                handoffs=[
                    {"from": "VP Engineering", "to": "Software Engineer", "context": "Feature requirements and specs"},
                    {"from": "Software Engineer", "to": "QA Engineer", "context": "Completed implementation"},
                    {"from": "QA Engineer", "to": "VP Engineering", "context": "Test results and issues"},
                    {"from": "VP Engineering", "to": "CTO", "context": "Ready for deployment"}
                ],
                commands=[
                    "/swarm generate SoftwareEngineer #implement feature, /analyze code #security review, /test automated #QA suite, /deploy staging #feature test, /approve technical #production release"
                ],
                success_criteria=[
                    "Feature meets requirements",
                    "Code passes all tests",
                    "Security review approved",
                    "Successfully deployed"
                ]
            ))
    
    def _generate_hybrid_command_examples(self) -> List[str]:
        """Generate example hybrid commands"""
        examples = []
        
        for workflow in self.generated_workflows:
            for cmd in workflow.commands[:2]:  # First 2 commands per workflow
                examples.append(cmd)
        
        return examples[:10]  # Return top 10 examples
    
    def interpret_command(self, command: str) -> Dict[str, Any]:
        """
        Interpret a command in natural language
        
        Example: /librarian interpret /swarm generate SeniorEngineer #implement auth
        Returns: "This command creates a swarm of AI agents led by a Senior Engineer role to implement an authentication system."
        """
        
        # Parse the command
        if command.startswith("/"):
            parts = command.split()
            if len(parts) >= 2:
                cmd = parts[0].replace("/", "")
                args = " ".join(parts[1:])
                
                # Split command and comment
                comment = ""
                if "#" in args:
                    cmd_args, comment = args.split("#", 1)
                    comment = comment.strip()
                    cmd_args = cmd_args.strip()
                else:
                    cmd_args = args
                
                # Generate natural language interpretation
                interpretation = self._generate_interpretation(cmd, cmd_args, comment)
                
                return {
                    "type": "interpretation",
                    "command": command,
                    "interpretation": interpretation,
                    "librarian_response": f"L: The command '{command}' means: {interpretation}"
                }
        
        return {
            "type": "error",
            "message": "Please provide a command to interpret",
            "example": "/librarian interpret /swarm generate Engineer #build feature"
        }
    
    def _generate_interpretation(self, cmd: str, args: str, comment: str) -> str:
        """Generate natural language interpretation of a command"""
        
        interpretations = {
            "swarm": f"Generate a swarm of AI agents with the role '{args}' to execute the task: {comment}",
            "analyze": f"Analyze '{args}' with focus on: {comment}",
            "plan": f"Create a plan for '{args}' considering: {comment}",
            "campaign": f"Launch a marketing campaign '{args}' with goal: {comment}",
            "content": f"Create content about '{args}' with context: {comment}",
            "lead": f"Manage lead '{args}' with details: {comment}",
            "proposal": f"Generate a proposal for '{args}' covering: {comment}",
            "budget": f"Create or manage budget '{args}' for: {comment}",
            "deploy": f"Deploy '{args}' to environment: {comment}",
            "test": f"Run tests on '{args}' with focus on: {comment}",
            "approve": f"Approve '{args}' based on: {comment}"
        }
        
        return interpretations.get(cmd, f"Execute command '{cmd}' with arguments '{args}' and context: {comment}")
    
    def command_to_natural(self, command: str) -> Dict[str, Any]:
        """
        Convert a command to natural language
        
        Example: /swarm generate Engineer #build feature
        Returns: "Please create a swarm of AI agents with the Engineer role to build the feature."
        """
        interpretation = self.interpret_command(command)
        
        if interpretation.get("type") == "interpretation":
            natural = interpretation["interpretation"].lower()
            # Make it more conversational
            if natural.startswith("generate"):
                natural = "Please " + natural
            elif natural.startswith("create"):
                natural = "Please " + natural
            elif natural.startswith("launch"):
                natural = "Please " + natural
            elif natural.startswith("analyze"):
                natural = "Please " + natural
            else:
                natural = natural.capitalize()
            
            return {
                "type": "natural_language",
                "command": command,
                "natural_language": natural,
                "librarian_response": f"L: In natural language, that command would be: '{natural}'"
            }
        
        return interpretation
    
    def natural_to_command(self, natural: str) -> Dict[str, Any]:
        """
        Convert natural language to command
        
        Example: "I want to create a swarm of engineers to build authentication"
        Returns: /swarm generate Engineer #build authentication
        """
        # Use LLM if available for better conversion
        if self.llm_client:
            try:
                prompt = f"""
Convert this natural language request to a Murphy System command.
Format: /command arguments #comment
Only return the command, nothing else.

Request: {natural}
"""
                response = self.llm_client.generate(prompt)
                command = response.strip()
                
                return {
                    "type": "command",
                    "natural_language": natural,
                    "command": command,
                    "librarian_response": f"L: I suggest the command: '{command}'"
                }
            except Exception as e:
                logger.error(f"LLM conversion failed: {e}")
        
        # Fallback: rule-based conversion
        return self._rule_based_natural_to_command(natural)
    
    def _rule_based_natural_to_command(self, natural: str) -> Dict[str, Any]:
        """Rule-based natural language to command conversion"""
        natural_lower = natural.lower()
        
        # Swarm generation
        if "swarm" in natural_lower or "team" in natural_lower or "agents" in natural_lower:
            if "engineer" in natural_lower:
                return {
                    "type": "command",
                    "natural_language": natural,
                    "command": "/swarm generate Engineer #implement system",
                    "librarian_response": "L: I suggest: /swarm generate Engineer #implement system"
                }
        
        # Analysis
        if "analyze" in natural_lower or "review" in natural_lower:
            return {
                "type": "command",
                "natural_language": natural,
                "command": "/analyze target #detailed review",
                "librarian_response": "L: I suggest: /analyze target #detailed review"
            }
        
        # Planning
        if "plan" in natural_lower or "strategy" in natural_lower:
            return {
                "type": "command",
                "natural_language": natural,
                "command": "/plan objective #strategic approach",
                "librarian_response": "L: I suggest: /plan objective #strategic approach"
            }
        
        return {
            "type": "suggestion",
            "message": "I need more context to convert this to a command.",
            "librarian_response": "L: Please provide more details about what you want to accomplish."
        }
    
    def generate_system(self, args: str) -> Dict[str, Any]:
        """
        Generate a complete system based on natural language request
        
        Example: /librarian generate complete AI software company automation
        """
        # This would trigger the full discovery and generation process
        return {
            "type": "system_generation",
            "message": f"Starting system generation for: {args}",
            "librarian_response": f"L: To generate a complete system for '{args}', I'll need to collect information about your business, organization, and requirements.",
            "action": "start_discovery"
        }
    
    def get_discovery_status(self) -> Dict[str, Any]:
        """Get current discovery status"""
        return {
            "type": "status",
            "phase": self.discovery_phase.value,
            "answers": self.discovery_answers,
            "org_chart_size": len(self.generated_org_chart),
            "gates_generated": len(self.generated_gates),
            "workflows_created": len(self.generated_workflows),
            "librarian_response": f"L: Current phase: {self.discovery_phase.value}"
        }
    
    def _get_librarian_help(self) -> Dict[str, Any]:
        """Get librarian help"""
        return {
            "type": "help",
            "message": "Murphy System Librarian Commands:",
            "commands": [
                "/librarian start - Begin system discovery and setup",
                "/librarian status - Show current discovery progress",
                "/librarian interpret <command> - Explain a command in natural language",
                "/librarian natural <command> - Convert command to natural language",
                "/librarian generate <request> - Generate complete system from request"
            ],
            "examples": [
                "/librarian interpret /swarm generate Engineer #build feature",
                "/librarian natural /swarm generate Engineer #build feature",
                "/librarian generate complete business automation for SaaS company"
            ],
            "librarian_response": "L: I'm here to help you set up complete business automation. Use these commands or just describe what you need."
        }
    
    def _handle_system_running(self, user_input: str) -> Dict[str, Any]:
        """Handle input when system is running"""
        # Try natural language to command conversion
        command_result = self.natural_to_command(user_input)
        
        if command_result.get("type") == "command":
            return {
                "type": "suggestion",
                "command": command_result["command"],
                "message": "I suggest this command:",
                "librarian_response": f"L: Based on your request, I suggest executing: {command_result['command']}"
            }
        
        return command_result
    
    def _unknown_librarian_command(self, action: str) -> Dict[str, Any]:
        """Handle unknown librarian command"""
        return {
            "type": "error",
            "message": f"Unknown librarian command: {action}",
            "suggestion": "Use /librarian help to see available commands"
        }
    
    def _unknown_discovery_phase(self) -> Dict[str, Any]:
        """Handle unknown discovery phase"""
        return {
            "type": "error",
            "message": "I'm not sure what to do next.",
            "suggestion": "Use /librarian status to see current progress"
        }