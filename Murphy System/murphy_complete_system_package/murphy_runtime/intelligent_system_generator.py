# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Intelligent System Generator
Generates complete business systems from natural language requests
Creates organizational charts, swarm agents, and automated workflows
"""

import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)


class BusinessRole:
    """Represents a role in the business"""
    
    def __init__(self, role_id: str, title: str, responsibilities: List[str],
                 commands: List[str], reports_to: str = None):
        self.role_id = role_id
        self.title = title
        self.responsibilities = responsibilities
        self.commands = commands
        self.reports_to = reports_to
        self.agent_id = None


class OrganizationalChart:
    """Represents the organizational structure"""
    
    def __init__(self, business_type: str):
        self.business_type = business_type
        self.roles = {}
        self.hierarchy = {}
        
    def add_role(self, role: BusinessRole):
        """Add a role to the org chart"""
        self.roles[role.role_id] = role
        
        if role.reports_to:
            if role.reports_to not in self.hierarchy:
                self.hierarchy[role.reports_to] = []
            self.hierarchy[role.reports_to].append(role.role_id)
    
    def get_role(self, role_id: str) -> Optional[BusinessRole]:
        """Get a role by ID"""
        return self.roles.get(role_id)
    
    def get_subordinates(self, role_id: str) -> List[BusinessRole]:
        """Get all subordinates of a role"""
        subordinate_ids = self.hierarchy.get(role_id, [])
        return [self.roles[rid] for rid in subordinate_ids if rid in self.roles]


class GeneratedSystem:
    """Represents a complete generated business system"""
    
    def __init__(self, system_id: str, business_type: str, user_request: str):
        self.system_id = system_id
        self.business_type = business_type
        self.user_request = user_request
        self.org_chart = OrganizationalChart(business_type)
        self.workflows = []
        self.agents = []
        self.automations = []
        self.required_info = []
        self.uploaded_docs = []
        self.analysis_results = {}
        self.status = "initializing"
        self.created_at = datetime.now()


class IntelligentSystemGenerator:
    """Generate complete business systems from natural language"""
    
    def __init__(self, llm_manager=None, librarian=None, swarm_system=None,
                 automation_system=None, calendar_scheduler=None):
        self.llm_manager = llm_manager
        self.librarian = librarian
        self.swarm_system = swarm_system
        self.automation_system = automation_system
        self.calendar_scheduler = calendar_scheduler
        self.generated_systems = {}
        
        # Business templates
        self.business_templates = {
            'publishing': self._get_publishing_template,
            'software': self._get_software_template,
            'consulting': self._get_consulting_template,
            'ecommerce': self._get_ecommerce_template,
            'marketing': self._get_marketing_template
        }
    
    def generate_system(self, user_request: str, business_type: str = None) -> Dict:
        """Generate a complete business system from user request"""
        
        system_id = f"sys_{uuid.uuid4().hex[:8]}"
        
        # Analyze request to determine business type
        if not business_type:
            business_type = self._analyze_business_type(user_request)
        
        logger.info(f"Generating system for: {business_type}")
        
        # Create system
        system = GeneratedSystem(system_id, business_type, user_request)
        self.generated_systems[system_id] = system
        
        # Step 1: Determine required information
        system.status = "gathering_requirements"
        required_info = self._determine_required_info(business_type, user_request)
        system.required_info = required_info
        
        # Step 2: Generate organizational chart
        system.status = "creating_org_chart"
        org_chart = self._generate_org_chart(business_type)
        system.org_chart = org_chart
        
        # Step 3: Create swarm agents for each role
        system.status = "creating_agents"
        agents = self._create_swarm_agents(system_id, org_chart)
        system.agents = agents
        
        # Step 4: Generate workflows
        system.status = "creating_workflows"
        workflows = self._generate_workflows(business_type, org_chart)
        system.workflows = workflows
        
        # Step 5: Setup automations
        system.status = "creating_automations"
        automations = self._setup_automations(business_type, workflows)
        system.automations = automations
        
        system.status = "ready"
        
        logger.info(f"✓ Generated system: {system_id} with {len(agents)} agents")
        
        return {
            'success': True,
            'system_id': system_id,
            'business_type': business_type,
            'required_info': required_info,
            'org_chart': self._org_chart_to_dict(org_chart),
            'agents': agents,
            'workflows': workflows,
            'automations': automations,
            'next_steps': [
                'Upload branding and documentation',
                'Review organizational chart',
                'Approve agent creation',
                'Start system execution'
            ]
        }
    
    def _analyze_business_type(self, user_request: str) -> str:
        """Analyze user request to determine business type"""
        
        request_lower = user_request.lower()
        
        if any(word in request_lower for word in ['publish', 'book', 'author', 'editor']):
            return 'publishing'
        elif any(word in request_lower for word in ['software', 'app', 'code', 'develop']):
            return 'software'
        elif any(word in request_lower for word in ['consult', 'advise', 'strategy']):
            return 'consulting'
        elif any(word in request_lower for word in ['shop', 'store', 'ecommerce', 'sell']):
            return 'ecommerce'
        elif any(word in request_lower for word in ['market', 'advertise', 'campaign']):
            return 'marketing'
        else:
            return 'general'
    
    def _determine_required_info(self, business_type: str, user_request: str) -> List[Dict]:
        """Determine what information is needed"""
        
        common_info = [
            {
                'category': 'branding',
                'items': ['Company name', 'Logo', 'Brand colors', 'Brand voice'],
                'priority': 'high'
            },
            {
                'category': 'documentation',
                'items': ['Business plan', 'Target audience', 'Value proposition'],
                'priority': 'high'
            }
        ]
        
        if business_type == 'publishing':
            specific_info = [
                {
                    'category': 'publishing_specifics',
                    'items': [
                        'Genre focus',
                        'Target bestseller topics',
                        'Sample published works',
                        'Author guidelines',
                        'Quality standards'
                    ],
                    'priority': 'high'
                },
                {
                    'category': 'marketing',
                    'items': [
                        'Marketing budget',
                        'Distribution channels',
                        'Author event preferences'
                    ],
                    'priority': 'medium'
                }
            ]
            return common_info + specific_info
        
        return common_info
    
    def _generate_org_chart(self, business_type: str) -> OrganizationalChart:
        """Generate organizational chart for business type"""
        
        if business_type in self.business_templates:
            return self.business_templates[business_type]()
        
        return self._get_general_template()
    
    def _get_publishing_template(self) -> OrganizationalChart:
        """Generate publishing company organizational chart"""
        
        org_chart = OrganizationalChart('publishing')
        
        # Executive level
        ceo = BusinessRole(
            role_id='ceo',
            title='Chief Executive Officer',
            responsibilities=[
                'Overall business strategy',
                'Final approval on major decisions',
                'Stakeholder management'
            ],
            commands=[
                '/business.sales',
                '/business.products',
                '/monitor.health'
            ]
        )
        org_chart.add_role(ceo)
        
        # Editorial Department
        editorial_director = BusinessRole(
            role_id='editorial_director',
            title='Editorial Director',
            responsibilities=[
                'Oversee all editorial operations',
                'Approve publication decisions',
                'Manage editorial team'
            ],
            commands=[
                '/artifact.list',
                '/artifact.view',
                '/swarm.status'
            ],
            reports_to='ceo'
        )
        org_chart.add_role(editorial_director)
        
        # Authors (AI Agents)
        author_agent = BusinessRole(
            role_id='author_agent',
            title='AI Author Agent',
            responsibilities=[
                'Research bestselling topics',
                'Generate book content',
                'Follow genre conventions',
                'Meet quality standards'
            ],
            commands=[
                '/llm.generate',
                '/librarian.search',
                '/artifact.create'
            ],
            reports_to='editorial_director'
        )
        org_chart.add_role(author_agent)
        
        # Editors (AI Agents)
        editor_agent = BusinessRole(
            role_id='editor_agent',
            title='AI Editor Agent',
            responsibilities=[
                'Review manuscript quality',
                'Check grammar and style',
                'Ensure consistency',
                'Provide feedback'
            ],
            commands=[
                '/artifact.view',
                '/artifact.update',
                '/llm.generate'
            ],
            reports_to='editorial_director'
        )
        org_chart.add_role(editor_agent)
        
        # Quality Control (AI Agents)
        qc_agent = BusinessRole(
            role_id='qc_agent',
            title='Quality Control Agent',
            responsibilities=[
                'Final quality check',
                'Verify formatting',
                'Check references',
                'Ensure publication standards'
            ],
            commands=[
                '/artifact.view',
                '/artifact.search',
                '/monitor.metrics'
            ],
            reports_to='editorial_director'
        )
        org_chart.add_role(qc_agent)
        
        # Human Reader (Human-in-the-Loop)
        human_reader = BusinessRole(
            role_id='human_reader',
            title='Human Reader / Approver',
            responsibilities=[
                'Final human review',
                'Approve for publication',
                'Provide creative feedback',
                'Make publication decisions'
            ],
            commands=[
                '/artifact.view',
                '/shadow.approve',
                '/shadow.reject'
            ],
            reports_to='editorial_director'
        )
        org_chart.add_role(human_reader)
        
        # Marketing Department
        marketing_director = BusinessRole(
            role_id='marketing_director',
            title='Marketing Director',
            responsibilities=[
                'Develop marketing strategies',
                'Manage campaigns',
                'Coordinate author events'
            ],
            commands=[
                '/business.marketing.campaign',
                '/business.sales',
                '/librarian.search'
            ],
            reports_to='ceo'
        )
        org_chart.add_role(marketing_director)
        
        # Marketing Agent
        marketing_agent = BusinessRole(
            role_id='marketing_agent',
            title='AI Marketing Agent',
            responsibilities=[
                'Create marketing plans',
                'Generate promotional content',
                'Schedule campaigns',
                'Track performance'
            ],
            commands=[
                '/llm.generate',
                '/business.marketing.campaign',
                '/automation/create'
            ],
            reports_to='marketing_director'
        )
        org_chart.add_role(marketing_agent)
        
        # Event Coordinator Agent
        event_agent = BusinessRole(
            role_id='event_agent',
            title='AI Event Coordinator',
            responsibilities=[
                'Schedule author signings',
                'Coordinate book launches',
                'Send invitations',
                'Manage RSVPs'
            ],
            commands=[
                '/automation/create',
                '/librarian.search',
                '/business.customers'
            ],
            reports_to='marketing_director'
        )
        org_chart.add_role(event_agent)
        
        return org_chart
    
    def _get_software_template(self) -> OrganizationalChart:
        """Generate software company organizational chart"""
        org_chart = OrganizationalChart('software')
        # Similar structure for software company
        return org_chart
    
    def _get_consulting_template(self) -> OrganizationalChart:
        """Generate consulting company organizational chart"""
        org_chart = OrganizationalChart('consulting')
        return org_chart
    
    def _get_ecommerce_template(self) -> OrganizationalChart:
        """Generate ecommerce company organizational chart"""
        org_chart = OrganizationalChart('ecommerce')
        return org_chart
    
    def _get_marketing_template(self) -> OrganizationalChart:
        """Generate marketing agency organizational chart"""
        org_chart = OrganizationalChart('marketing')
        return org_chart
    
    def _get_general_template(self) -> OrganizationalChart:
        """Generate general business organizational chart"""
        org_chart = OrganizationalChart('general')
        return org_chart
    
    def _create_swarm_agents(self, system_id: str, org_chart: OrganizationalChart) -> List[Dict]:
        """Create swarm agents for each role"""
        
        agents = []
        
        for role_id, role in org_chart.roles.items():
            # Skip human roles
            if 'human' in role.title.lower():
                continue
            
            agent = {
                'agent_id': f"{system_id}_{role_id}",
                'role_id': role_id,
                'title': role.title,
                'type': 'ai_agent',
                'responsibilities': role.responsibilities,
                'commands': role.commands,
                'reports_to': role.reports_to,
                'status': 'ready',
                'created_at': datetime.now().isoformat()
            }
            
            agents.append(agent)
            role.agent_id = agent['agent_id']
        
        return agents
    
    def _generate_workflows(self, business_type: str, org_chart: OrganizationalChart) -> List[Dict]:
        """Generate workflows for the business"""
        
        workflows = []
        
        if business_type == 'publishing':
            # Book Creation Workflow
            book_workflow = {
                'workflow_id': f'workflow_{uuid.uuid4().hex[:8]}',
                'name': 'Book Creation and Publication',
                'description': 'Complete workflow from topic research to publication',
                'steps': [
                    {
                        'step': 1,
                        'name': 'Topic Research',
                        'agent': 'author_agent',
                        'commands': [
                            '/librarian.search bestselling topics',
                            '/llm.generate topic analysis'
                        ],
                        'time_quota': 300
                    },
                    {
                        'step': 2,
                        'name': 'Content Generation',
                        'agent': 'author_agent',
                        'commands': [
                            '/artifact.create book manuscript',
                            '/llm.generate chapter content'
                        ],
                        'time_quota': 1800
                    },
                    {
                        'step': 3,
                        'name': 'Editorial Review',
                        'agent': 'editor_agent',
                        'commands': [
                            '/artifact.view manuscript',
                            '/artifact.update corrections',
                            '/llm.generate editorial feedback'
                        ],
                        'time_quota': 900
                    },
                    {
                        'step': 4,
                        'name': 'Quality Control',
                        'agent': 'qc_agent',
                        'commands': [
                            '/artifact.view manuscript',
                            '/artifact.search quality issues',
                            '/monitor.metrics quality_score'
                        ],
                        'time_quota': 600
                    },
                    {
                        'step': 5,
                        'name': 'Human Review',
                        'agent': 'human_reader',
                        'commands': [
                            '/artifact.view manuscript',
                            '/shadow.approve publication'
                        ],
                        'time_quota': 3600,
                        'requires_human': True
                    },
                    {
                        'step': 6,
                        'name': 'Marketing Plan',
                        'agent': 'marketing_agent',
                        'commands': [
                            '/llm.generate marketing plan',
                            '/business.marketing.campaign create'
                        ],
                        'time_quota': 600
                    },
                    {
                        'step': 7,
                        'name': 'Event Scheduling',
                        'agent': 'event_agent',
                        'commands': [
                            '/automation/create book signing',
                            '/automation/create launch event'
                        ],
                        'time_quota': 300
                    }
                ],
                'triggers': ['new_book_request', 'scheduled_production']
            }
            workflows.append(book_workflow)
        
        return workflows
    
    def _setup_automations(self, business_type: str, workflows: List[Dict]) -> List[Dict]:
        """Setup automations for the business"""
        
        automations = []
        
        if business_type == 'publishing':
            # Daily topic research
            automations.append({
                'name': 'Daily Bestseller Research',
                'type': 'maintenance',
                'schedule': 'every 24 hours',
                'command': '/librarian.search bestselling topics'
            })
            
            # Weekly quality review
            automations.append({
                'name': 'Weekly Quality Metrics',
                'type': 'maintenance',
                'schedule': 'every 168 hours',
                'command': '/monitor.metrics quality_control'
            })
            
            # Marketing follow-ups
            automations.append({
                'name': 'Post-Publication Marketing',
                'type': 'sales_followup',
                'schedule': 'after publication',
                'command': '/business.marketing.campaign launch'
            })
        
        return automations
    
    def upload_documentation(self, system_id: str, doc_type: str,
                           content: str, metadata: Dict = None) -> Dict:
        """Upload documentation for system analysis"""
        
        if system_id not in self.generated_systems:
            return {'success': False, 'error': 'System not found'}
        
        system = self.generated_systems[system_id]
        
        doc = {
            'doc_id': f"doc_{uuid.uuid4().hex[:8]}",
            'type': doc_type,
            'content': content,
            'metadata': metadata or {},
            'uploaded_at': datetime.now().isoformat()
        }
        
        system.uploaded_docs.append(doc)
        
        # Analyze document
        if self.llm_manager:
            analysis = self._analyze_document(doc, system.business_type)
            system.analysis_results[doc['doc_id']] = analysis
        
        logger.info(f"✓ Uploaded document: {doc_type} for system {system_id}")
        
        return {
            'success': True,
            'doc_id': doc['doc_id'],
            'system_id': system_id,
            'analysis': system.analysis_results.get(doc['doc_id'])
        }
    
    def _analyze_document(self, doc: Dict, business_type: str) -> Dict:
        """Analyze uploaded document"""
        
        if not self.llm_manager:
            return {'note': 'LLM not available for analysis'}
        
        prompt = f"""Analyze this {doc['type']} document for a {business_type} business:

{doc['content'][:1000]}

Extract:
1. Key information relevant to the business
2. Brand voice and style
3. Target audience insights
4. Quality standards
5. Any specific requirements or constraints

Provide a structured analysis."""
        
        analysis = self.llm_manager.generate(prompt=prompt, max_tokens=500)
        
        return {
            'summary': analysis[:200],
            'full_analysis': analysis,
            'analyzed_at': datetime.now().isoformat()
        }
    
    def start_system(self, system_id: str) -> Dict:
        """Start executing the generated system"""
        
        if system_id not in self.generated_systems:
            return {'success': False, 'error': 'System not found'}
        
        system = self.generated_systems[system_id]
        
        if system.status != 'ready':
            return {
                'success': False,
                'error': f'System not ready (status: {system.status})'
            }
        
        # Create swarm agents
        if self.swarm_system:
            for agent in system.agents:
                # Create agent in swarm system
                pass
        
        # Setup workflows
        if self.calendar_scheduler:
            for workflow in system.workflows:
                # Create scheduled tasks for workflows
                pass
        
        # Setup automations
        if self.automation_system:
            for automation in system.automations:
                # Create automations
                pass
        
        system.status = 'running'
        
        logger.info(f"✓ Started system: {system_id}")
        
        return {
            'success': True,
            'system_id': system_id,
            'status': 'running',
            'agents': len(system.agents),
            'workflows': len(system.workflows),
            'automations': len(system.automations)
        }
    
    def get_system(self, system_id: str) -> Optional[Dict]:
        """Get system details"""
        if system_id in self.generated_systems:
            system = self.generated_systems[system_id]
            return {
                'system_id': system.system_id,
                'business_type': system.business_type,
                'user_request': system.user_request,
                'status': system.status,
                'org_chart': self._org_chart_to_dict(system.org_chart),
                'agents': system.agents,
                'workflows': system.workflows,
                'automations': system.automations,
                'required_info': system.required_info,
                'uploaded_docs': len(system.uploaded_docs),
                'created_at': system.created_at.isoformat()
            }
        return None
    
    def _org_chart_to_dict(self, org_chart: OrganizationalChart) -> Dict:
        """Convert org chart to dictionary"""
        roles = []
        for role in org_chart.roles.values():
            roles.append({
                'role_id': role.role_id,
                'title': role.title,
                'responsibilities': role.responsibilities,
                'commands': role.commands,
                'reports_to': role.reports_to,
                'agent_id': role.agent_id
            })
        
        return {
            'business_type': org_chart.business_type,
            'roles': roles,
            'hierarchy': org_chart.hierarchy
        }


# Global instance
_system_generator = None

def get_system_generator(llm_manager=None, librarian=None, swarm_system=None,
                        automation_system=None, calendar_scheduler=None) -> IntelligentSystemGenerator:
    """Get or create system generator instance"""
    global _system_generator
    if _system_generator is None:
        _system_generator = IntelligentSystemGenerator(
            llm_manager=llm_manager,
            librarian=librarian,
            swarm_system=swarm_system,
            automation_system=automation_system,
            calendar_scheduler=calendar_scheduler
        )
    return _system_generator