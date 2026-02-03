"""
Murphy System - Librarian System Commands
Clear commands for Librarian to generate and manage complete business systems
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class LibrarianSystemCommands:
    """Commands that Librarian can use to generate complete systems"""
    
    def __init__(self, system_generator, calendar_scheduler, librarian_integration):
        self.system_generator = system_generator
        self.calendar_scheduler = calendar_scheduler
        self.librarian_integration = librarian_integration
        
    def generate_business_system(self, user_request: str) -> Dict:
        """
        Main command: Generate a complete business system from user request
        
        Example: "I want to use you to run my publishing company"
        
        This will:
        1. Analyze the request
        2. Determine required information
        3. Create organizational chart
        4. Generate AI agents for each role
        5. Setup workflows
        6. Create automations
        """
        
        logger.info(f"Generating business system from: {user_request}")
        
        # Generate the system
        result = self.system_generator.generate_system(user_request)
        
        if not result['success']:
            return result
        
        system_id = result['system_id']
        
        # Store system info in Librarian
        if self.librarian_integration:
            self.librarian_integration.librarian.store_knowledge(
                content=f"Generated business system: {result['business_type']}\nRequest: {user_request}",
                tags=['system_generation', result['business_type'], 'business'],
                metadata={
                    'system_id': system_id,
                    'business_type': result['business_type'],
                    'agents': len(result['agents']),
                    'workflows': len(result['workflows'])
                }
            )
        
        return {
            'success': True,
            'message': f"Generated {result['business_type']} business system",
            'system_id': system_id,
            'next_command': f"upload_documentation('{system_id}', ...)",
            'result': result
        }
    
    def upload_documentation(self, system_id: str, doc_type: str, content: str) -> Dict:
        """
        Upload documentation for system analysis
        
        Doc types: 'branding', 'business_plan', 'samples', 'guidelines', 'standards'
        
        Example: upload_documentation('sys_abc123', 'branding', 'Company: XYZ Publishing...')
        """
        
        result = self.system_generator.upload_documentation(
            system_id=system_id,
            doc_type=doc_type,
            content=content
        )
        
        return {
            'success': result['success'],
            'message': f"Uploaded {doc_type} documentation",
            'analysis': result.get('analysis'),
            'next_command': "analyze_and_decide_needs(...)"
        }
    
    def analyze_and_decide_needs(self, system_id: str) -> Dict:
        """
        Analyze all uploaded documentation and decide what else is needed
        
        This command:
        1. Reviews all uploaded docs
        2. Analyzes against business requirements
        3. Identifies gaps
        4. Suggests what to create next
        """
        
        system = self.system_generator.get_system(system_id)
        
        if not system:
            return {'success': False, 'error': 'System not found'}
        
        # Analyze what's been uploaded
        uploaded_types = [doc['type'] for doc in system.get('uploaded_docs', [])]
        required_info = system.get('required_info', [])
        
        # Determine gaps
        gaps = []
        for req in required_info:
            category = req['category']
            if category not in uploaded_types:
                gaps.append({
                    'category': category,
                    'items': req['items'],
                    'priority': req['priority']
                })
        
        # Decide what to create
        to_create = []
        
        if system['business_type'] == 'publishing':
            to_create = [
                {
                    'item': 'Author guidelines document',
                    'command': 'create_author_guidelines',
                    'priority': 'high'
                },
                {
                    'item': 'Quality control checklist',
                    'command': 'create_qc_checklist',
                    'priority': 'high'
                },
                {
                    'item': 'Marketing templates',
                    'command': 'create_marketing_templates',
                    'priority': 'medium'
                },
                {
                    'item': 'Event planning templates',
                    'command': 'create_event_templates',
                    'priority': 'medium'
                }
            ]
        
        return {
            'success': True,
            'gaps': gaps,
            'to_create': to_create,
            'next_command': 'generate_swarm_agents(...)'
        }
    
    def generate_swarm_agents(self, system_id: str) -> Dict:
        """
        Generate swarm agents for all roles in the organizational chart
        
        For publishing company, this creates:
        - Author agents (research and write)
        - Editor agents (review and improve)
        - QC agents (quality control)
        - Marketing agents (promote and market)
        - Event agents (coordinate signings and launches)
        """
        
        system = self.system_generator.get_system(system_id)
        
        if not system:
            return {'success': False, 'error': 'System not found'}
        
        agents = system.get('agents', [])
        
        # Create command chains for each agent
        agent_tasks = []
        
        for agent in agents:
            if 'author' in agent['title'].lower():
                # Author agent workflow
                task = {
                    'agent_id': agent['agent_id'],
                    'workflow': 'book_creation',
                    'command_chain': [
                        '/librarian.search bestselling topics',
                        '/llm.generate topic analysis',
                        '/artifact.create book outline',
                        '/llm.generate chapter 1',
                        '/llm.generate chapter 2',
                        # ... more chapters
                        '/artifact.create complete manuscript'
                    ],
                    'time_quotas': [300, 600, 300, 600, 600, 300]
                }
                agent_tasks.append(task)
                
            elif 'editor' in agent['title'].lower():
                # Editor agent workflow
                task = {
                    'agent_id': agent['agent_id'],
                    'workflow': 'editorial_review',
                    'command_chain': [
                        '/artifact.view manuscript',
                        '/llm.generate editorial analysis',
                        '/artifact.update corrections',
                        '/llm.generate feedback report'
                    ],
                    'time_quotas': [300, 600, 600, 300]
                }
                agent_tasks.append(task)
                
            elif 'qc' in agent['title'].lower() or 'quality' in agent['title'].lower():
                # QC agent workflow
                task = {
                    'agent_id': agent['agent_id'],
                    'workflow': 'quality_control',
                    'command_chain': [
                        '/artifact.view manuscript',
                        '/artifact.search quality issues',
                        '/monitor.metrics quality_score',
                        '/llm.generate qc report'
                    ],
                    'time_quotas': [300, 300, 300, 300]
                }
                agent_tasks.append(task)
                
            elif 'marketing' in agent['title'].lower():
                # Marketing agent workflow
                task = {
                    'agent_id': agent['agent_id'],
                    'workflow': 'marketing_campaign',
                    'command_chain': [
                        '/librarian.search marketing strategies',
                        '/llm.generate marketing plan',
                        '/business.marketing.campaign create',
                        '/automation/create email campaign'
                    ],
                    'time_quotas': [300, 600, 300, 300]
                }
                agent_tasks.append(task)
                
            elif 'event' in agent['title'].lower():
                # Event agent workflow
                task = {
                    'agent_id': agent['agent_id'],
                    'workflow': 'event_coordination',
                    'command_chain': [
                        '/librarian.search venue options',
                        '/automation/create book signing',
                        '/automation/create launch event',
                        '/business.customers send invitations'
                    ],
                    'time_quotas': [300, 300, 300, 300]
                }
                agent_tasks.append(task)
        
        return {
            'success': True,
            'agents_created': len(agent_tasks),
            'agent_tasks': agent_tasks,
            'next_command': 'create_scheduled_workflows(...)'
        }
    
    def create_scheduled_workflows(self, system_id: str) -> Dict:
        """
        Create scheduled workflows with command chains and time quotas
        
        This creates the complete automation pipeline:
        1. Author creates content (with time quota)
        2. Editor reviews (with time quota)
        3. QC checks (with time quota)
        4. Human approves (can request more time)
        5. Marketing plans (with time quota)
        6. Events scheduled (with time quota)
        """
        
        system = self.system_generator.get_system(system_id)
        
        if not system:
            return {'success': False, 'error': 'System not found'}
        
        workflows = system.get('workflows', [])
        scheduled_tasks = []
        
        for workflow in workflows:
            # Extract command chains from workflow steps
            command_chains = []
            time_quotas = []
            
            for step in workflow.get('steps', []):
                command_chains.append(step.get('commands', []))
                time_quotas.append(step.get('time_quota', 300))
            
            # Create scheduled task
            task_result = self.calendar_scheduler.create_task(
                name=workflow['name'],
                description=workflow['description'],
                command_chains=command_chains,
                time_quotas=time_quotas,
                priority='high',
                metadata={'workflow_id': workflow['workflow_id']}
            )
            
            scheduled_tasks.append(task_result)
        
        return {
            'success': True,
            'workflows_scheduled': len(scheduled_tasks),
            'tasks': scheduled_tasks,
            'next_command': 'start_system(...)'
        }
    
    def start_system(self, system_id: str) -> Dict:
        """
        Start the complete business system
        
        This activates:
        - All AI agents
        - All workflows
        - All automations
        - Scheduler for recurring tasks
        """
        
        result = self.system_generator.start_system(system_id)
        
        if not result['success']:
            return result
        
        # Start scheduler
        if self.calendar_scheduler:
            self.calendar_scheduler.running = True
        
        return {
            'success': True,
            'message': 'Business system is now running!',
            'system_id': system_id,
            'status': 'operational',
            'agents': result['agents'],
            'workflows': result['workflows'],
            'automations': result['automations']
        }
    
    def get_system_status(self, system_id: str) -> Dict:
        """Get current status of the business system"""
        
        system = self.system_generator.get_system(system_id)
        
        if not system:
            return {'success': False, 'error': 'System not found'}
        
        # Get task statuses
        tasks = self.calendar_scheduler.list_tasks()
        system_tasks = [t for t in tasks if t.get('metadata', {}).get('system_id') == system_id]
        
        return {
            'success': True,
            'system_id': system_id,
            'status': system['status'],
            'business_type': system['business_type'],
            'agents': len(system['agents']),
            'active_workflows': len([t for t in system_tasks if t['status'] == 'running']),
            'completed_workflows': len([t for t in system_tasks if t['status'] == 'completed']),
            'pending_workflows': len([t for t in system_tasks if t['status'] == 'pending'])
        }
    
    def human_approve_output(self, system_id: str, artifact_id: str, approved: bool,
                           feedback: str = None) -> Dict:
        """
        Human-in-the-loop approval for generated content
        
        If approved: Continue to next step (marketing, events)
        If rejected: Send back to editor with feedback
        """
        
        if approved:
            # Continue workflow
            return {
                'success': True,
                'message': 'Content approved, proceeding to marketing',
                'next_steps': ['marketing_plan', 'event_scheduling']
            }
        else:
            # Send back for revision
            return {
                'success': True,
                'message': 'Content needs revision',
                'feedback': feedback,
                'next_steps': ['editorial_review', 'quality_control']
            }
    
    def get_available_commands(self) -> List[Dict]:
        """Get all available Librarian system commands"""
        
        return [
            {
                'command': 'generate_business_system',
                'description': 'Generate complete business system from user request',
                'example': 'generate_business_system("I want to run a publishing company")',
                'parameters': ['user_request']
            },
            {
                'command': 'upload_documentation',
                'description': 'Upload branding, guidelines, or samples',
                'example': 'upload_documentation("sys_123", "branding", "Company: XYZ...")',
                'parameters': ['system_id', 'doc_type', 'content']
            },
            {
                'command': 'analyze_and_decide_needs',
                'description': 'Analyze docs and decide what to create',
                'example': 'analyze_and_decide_needs("sys_123")',
                'parameters': ['system_id']
            },
            {
                'command': 'generate_swarm_agents',
                'description': 'Create AI agents for all organizational roles',
                'example': 'generate_swarm_agents("sys_123")',
                'parameters': ['system_id']
            },
            {
                'command': 'create_scheduled_workflows',
                'description': 'Setup workflows with time quotas and command chains',
                'example': 'create_scheduled_workflows("sys_123")',
                'parameters': ['system_id']
            },
            {
                'command': 'start_system',
                'description': 'Activate the complete business system',
                'example': 'start_system("sys_123")',
                'parameters': ['system_id']
            },
            {
                'command': 'get_system_status',
                'description': 'Check current system status',
                'example': 'get_system_status("sys_123")',
                'parameters': ['system_id']
            },
            {
                'command': 'human_approve_output',
                'description': 'Human approval for generated content',
                'example': 'human_approve_output("sys_123", "artifact_456", True)',
                'parameters': ['system_id', 'artifact_id', 'approved', 'feedback']
            }
        ]


# Global instance
_librarian_commands = None

def get_librarian_commands(system_generator, calendar_scheduler, 
                          librarian_integration) -> LibrarianSystemCommands:
    """Get or create librarian commands instance"""
    global _librarian_commands
    if _librarian_commands is None:
        _librarian_commands = LibrarianSystemCommands(
            system_generator=system_generator,
            calendar_scheduler=calendar_scheduler,
            librarian_integration=librarian_integration
        )
    return _librarian_commands