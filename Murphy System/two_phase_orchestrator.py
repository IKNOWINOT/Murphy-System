"""
Murphy Two-Phase Orchestrator

Phase 1: GENERATIVE SETUP (Carving from Infinity)
- Dial down to right planet, data, regulations, constraints
- Generate agents that fit discovered constraints
- One-time setup per automation

Phase 2: PRODUCTION EXECUTION (Automated Repeat)
- Execute the configured automation
- Produce business deliverables
- Run on schedule or trigger

Copyright © 2020 Inoni Limited Liability Company
Created by: Corey Post
License: BSL 1.1
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# PHASE 1: GENERATIVE SETUP
# ============================================================================

class InformationGatheringAgent:
    """
    Gathers information to carve down from infinity
    - What platforms/systems?
    - What data sources?
    - What schedule?
    - What approvals needed?
    """
    def __init__(self):
        self.gathered_info = {}
        
    # Keyword-based platform catalogue used for intelligent extraction.
    PLATFORM_KEYWORDS: Dict[str, str] = {
        'wordpress': 'wordpress',
        'medium': 'medium',
        'twitter': 'twitter',
        'linkedin': 'linkedin',
        'github': 'github',
        'slack': 'slack',
        'jira': 'jira',
        'salesforce': 'salesforce',
        'shopify': 'shopify',
        'stripe': 'stripe',
        'aws': 'aws',
        'azure': 'azure',
        'gcp': 'gcp',
        'docker': 'docker',
        'kubernetes': 'kubernetes',
        'notion': 'notion',
        'google docs': 'google_docs',
        'google sheets': 'google_sheets',
        'hubspot': 'hubspot',
        'mailchimp': 'mailchimp',
        'sendgrid': 'sendgrid',
        'twilio': 'twilio',
        'zapier': 'zapier',
    }

    # Keywords that indicate data/content sources.
    SOURCE_KEYWORDS: Dict[str, str] = {
        'notion': 'notion',
        'google docs': 'google_docs',
        'google sheets': 'google_sheets',
        'database': 'database',
        'csv': 'csv',
        'api': 'api',
        'rss': 'rss',
        'file': 'filesystem',
    }

    # Schedule keywords.
    SCHEDULE_KEYWORDS: Dict[str, str] = {
        'hourly': 'hourly',
        'daily': 'daily',
        'weekly': 'weekly',
        'monthly': 'monthly',
        'real-time': 'realtime',
        'realtime': 'realtime',
        'on demand': 'manual',
        'manual': 'manual',
    }

    def gather(self, request: str, domain: str) -> Dict[str, Any]:
        """Gather information through intelligent keyword analysis.

        Analyses the natural-language *request* to extract:
        * target platforms / services
        * data or content sources
        * desired schedule
        * whether human approval is required
        * complexity estimate and recommended automation type

        The extraction uses expanded keyword catalogues so that a wider
        range of user requests produce meaningful results without requiring
        follow-up questions.
        """
        platforms = self._extract_platforms(request)
        source = self._extract_source(request)
        schedule = self._extract_schedule(request)
        approval = self._needs_approval(request)
        complexity = self._estimate_complexity(request, platforms)
        automation_type = self._recommend_automation_type(domain, complexity)

        info = {
            'domain': domain,
            'request': request,
            'platforms': platforms,
            'content_source': source,
            'schedule': schedule,
            'approval_required': approval,
            'complexity': complexity,
            'automation_type': automation_type,
        }

        self.gathered_info = info
        return info

    def _extract_platforms(self, request: str) -> List[str]:
        """Extract target platforms from request using the keyword catalogue."""
        request_lower = request.lower()
        platforms = []
        for keyword, platform in self.PLATFORM_KEYWORDS.items():
            if keyword in request_lower and platform not in platforms:
                platforms.append(platform)
        return platforms
        
    def _extract_source(self, request: str) -> str:
        """Extract content/data source from request using the keyword catalogue."""
        request_lower = request.lower()
        for keyword, source in self.SOURCE_KEYWORDS.items():
            if keyword in request_lower:
                return source
        return 'manual'

    def _extract_schedule(self, request: str) -> str:
        """Extract schedule from request using the keyword catalogue."""
        request_lower = request.lower()
        for keyword, schedule in self.SCHEDULE_KEYWORDS.items():
            if keyword in request_lower:
                return schedule
        return 'manual'
        
    def _needs_approval(self, request: str) -> bool:
        """Determine if approval needed"""
        return 'approval' in request.lower() or 'review' in request.lower()

    def _estimate_complexity(self, request: str, platforms: List[str]) -> str:
        """Estimate the complexity of the requested automation.

        Returns one of ``'low'``, ``'medium'``, or ``'high'`` based on
        the number of platforms involved and signal words in the request.
        """
        request_lower = request.lower()
        high_signals = ['complex', 'enterprise', 'multi-step', 'multi step',
                        'orchestrate', 'ci/cd', 'pipeline']
        if any(s in request_lower for s in high_signals) or len(platforms) >= 4:
            return 'high'
        if len(platforms) >= 2:
            return 'medium'
        return 'low'

    def _recommend_automation_type(self, domain: str, complexity: str) -> str:
        """Recommend an automation type based on domain and complexity.

        Maps the combination to one of: ``'agent_swarm'``,
        ``'content_api'``, ``'sensor_actuator'``, or ``'hybrid'``.
        """
        if complexity == 'high':
            return 'hybrid'
        domain_map = {
            'publishing': 'content_api',
            'e-commerce': 'hybrid',
            'factory': 'sensor_actuator',
            'devops': 'command_system',
            'marketing': 'content_api',
            'research': 'agent_swarm',
        }
        return domain_map.get(domain, 'agent_swarm')

class RegulationDiscoveryAgent:
    """
    Discovers regulations, constraints, and requirements
    - Platform APIs and rate limits
    - Content policies
    - Legal requirements (GDPR, copyright, etc.)
    - Technical constraints
    """
    def __init__(self):
        self.regulations = {}
        
    def discover(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Discover regulations for the given information
        """
        regulations = {
            'platform_apis': self._discover_platform_apis(info.get('platforms', [])),
            'content_policies': self._discover_content_policies(info.get('platforms', [])),
            'legal_requirements': self._discover_legal_requirements(info),
            'technical_constraints': self._discover_technical_constraints(info)
        }
        
        self.regulations = regulations
        return regulations
        
    def _discover_platform_apis(self, platforms: List[str]) -> Dict[str, Any]:
        """Discover platform API requirements"""
        apis = {}
        for platform in platforms:
            if platform == 'wordpress':
                apis['wordpress'] = {
                    'api_type': 'REST',
                    'rate_limit': 100,
                    'auth': 'oauth',
                    'docs': 'https://developer.wordpress.org/rest-api/'
                }
            elif platform == 'medium':
                apis['medium'] = {
                    'api_type': 'REST',
                    'rate_limit': 50,
                    'auth': 'token',
                    'docs': 'https://github.com/Medium/medium-api-docs'
                }
        return apis
        
    def _discover_content_policies(self, platforms: List[str]) -> Dict[str, Any]:
        """Discover content policies"""
        return {
            'no_spam': True,
            'attribution_required': True,
            'original_content': True
        }
        
    def _discover_legal_requirements(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """Discover legal requirements"""
        return {
            'gdpr': True,
            'copyright': True,
            'privacy_policy': True
        }
        
    def _discover_technical_constraints(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """Discover technical constraints"""
        return {
            'max_retries': 3,
            'timeout': 30,
            'error_handling': 'retry_with_backoff'
        }

class ConstraintCompiler:
    """
    Compiles all constraints into a unified format
    - Technical constraints (rate limits, timeouts)
    - Business constraints (approval workflows)
    - Legal constraints (compliance requirements)
    - Operational constraints (error handling, monitoring)
    """
    def __init__(self):
        self.constraints = {}
        
    def compile(self, info: Dict[str, Any], regulations: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compile all constraints
        """
        constraints = {
            'technical': self._compile_technical(regulations),
            'business': self._compile_business(info),
            'legal': self._compile_legal(regulations),
            'operational': self._compile_operational(regulations)
        }
        
        self.constraints = constraints
        return constraints
        
    def _compile_technical(self, regulations: Dict[str, Any]) -> Dict[str, Any]:
        """Compile technical constraints"""
        return {
            'rate_limits': regulations.get('platform_apis', {}),
            'timeouts': regulations.get('technical_constraints', {}).get('timeout', 30),
            'max_retries': regulations.get('technical_constraints', {}).get('max_retries', 3)
        }
        
    def _compile_business(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """Compile business constraints"""
        return {
            'approval_required': info.get('approval_required', False),
            'quality_threshold': 0.8,
            'schedule': info.get('schedule', 'manual')
        }
        
    def _compile_legal(self, regulations: Dict[str, Any]) -> Dict[str, Any]:
        """Compile legal constraints"""
        return regulations.get('legal_requirements', {})
        
    def _compile_operational(self, regulations: Dict[str, Any]) -> Dict[str, Any]:
        """Compile operational constraints"""
        return {
            'error_handling': regulations.get('technical_constraints', {}).get('error_handling', 'retry'),
            'monitoring': True,
            'logging': True
        }

class AgentGenerator:
    """
    Generates agents from templates + constraints
    - Takes domain swarm template
    - Applies discovered constraints
    - Creates configured agents ready to execute
    """
    def __init__(self):
        self.generated_agents = []
        
    def generate(self, domain: str, info: Dict[str, Any], constraints: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate agents for the domain with constraints
        """
        agents = []
        
        # Get template for domain
        template = self._get_domain_template(domain)
        
        # Generate agents from template
        for agent_spec in template:
            agent = self._create_agent(agent_spec, info, constraints)
            agents.append(agent)
            
        self.generated_agents = agents
        return agents
        
    def _get_domain_template(self, domain: str) -> List[Dict[str, Any]]:
        """Get agent template for domain"""
        templates = {
            'publishing': [
                {'type': 'ContentFetcher', 'role': 'fetch_content'},
                {'type': 'ContentValidator', 'role': 'validate_quality'},
                {'type': 'ApprovalGate', 'role': 'human_approval'},
                {'type': 'Publisher', 'role': 'publish_content'},
                {'type': 'ErrorHandler', 'role': 'handle_errors'}
            ],
            'e-commerce': [
                {'type': 'InventoryManager', 'role': 'manage_inventory'},
                {'type': 'OrderProcessor', 'role': 'process_orders'},
                {'type': 'PaymentHandler', 'role': 'handle_payments'},
                {'type': 'ShippingCoordinator', 'role': 'coordinate_shipping'}
            ]
        }
        return templates.get(domain, [])
        
    def _create_agent(self, spec: Dict[str, Any], info: Dict[str, Any], constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Create configured agent from spec"""
        return {
            'id': f"{spec['type']}_{datetime.now().timestamp()}",
            'type': spec['type'],
            'role': spec['role'],
            'constraints': constraints,
            'config': {
                'platforms': info.get('platforms', []),
                'source': info.get('content_source'),
                'schedule': info.get('schedule')
            }
        }

class SandboxManager:
    """
    Manages sandbox environments for automation execution
    - Creates isolated environments
    - Installs dependencies
    - Manages credentials
    - Sets up deliverable output directories
    """
    def __init__(self):
        self.sandboxes = {}
        
    def create_sandbox(self, automation_id: str, agents: List[Dict[str, Any]], constraints: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create sandbox for automation
        """
        sandbox = {
            'id': f"sandbox_{automation_id}",
            'automation_id': automation_id,
            'environment': self._create_environment(),
            'dependencies': self._install_dependencies(agents),
            'credentials': self._setup_credentials(agents),
            'output_dir': self._create_output_dir(automation_id)
        }
        
        self.sandboxes[automation_id] = sandbox
        return sandbox
        
    def _create_environment(self) -> Dict[str, Any]:
        """Create isolated environment"""
        return {
            'type': 'docker',
            'image': 'murphy-runtime:latest',
            'isolated': True
        }
        
    def _install_dependencies(self, agents: List[Dict[str, Any]]) -> List[str]:
        """Install required dependencies"""
        deps = set()
        for agent in agents:
            if agent['type'] == 'Publisher':
                deps.add('wordpress-api')
                deps.add('medium-api')
        return list(deps)
        
    def _setup_credentials(self, agents: List[Dict[str, Any]]) -> Dict[str, str]:
        """Setup credentials"""
        return {
            'wordpress_token': 'PLACEHOLDER',
            'medium_token': 'PLACEHOLDER'
        }
        
    def _create_output_dir(self, automation_id: str) -> str:
        """Create output directory"""
        return f"/workspace/deliverables/{automation_id}"

class GenerativeSetupOrchestrator:
    """
    Phase 1: Orchestrates the generative setup process
    """
    def __init__(self):
        self.info_gatherer = InformationGatheringAgent()
        self.regulation_discoverer = RegulationDiscoveryAgent()
        self.constraint_compiler = ConstraintCompiler()
        self.agent_generator = AgentGenerator()
        self.sandbox_manager = SandboxManager()
        
    def execute_phase1(self, request: str, domain: str) -> Dict[str, Any]:
        """
        Execute Phase 1: Generative Setup
        """
        logger.info("=" * 60)
        logger.info("PHASE 1: GENERATIVE SETUP")
        logger.info("=" * 60)
        
        # 1. Gather information
        logger.info("1. Gathering information...")
        info = self.info_gatherer.gather(request, domain)
        logger.info(f"   Gathered: {info}")
        
        # 2. Discover regulations
        logger.info("2. Discovering regulations...")
        regulations = self.regulation_discoverer.discover(info)
        logger.info(f"   Regulations: {len(regulations)} categories")
        
        # 3. Compile constraints
        logger.info("3. Compiling constraints...")
        constraints = self.constraint_compiler.compile(info, regulations)
        logger.info(f"   Constraints: {len(constraints)} categories")
        
        # 4. Generate agents
        logger.info("4. Generating agents...")
        agents = self.agent_generator.generate(domain, info, constraints)
        logger.info(f"   Generated: {len(agents)} agents")
        
        # 5. Setup sandbox
        automation_id = f"auto_{datetime.now().timestamp()}"
        logger.info(f"5. Setting up sandbox for {automation_id}...")
        sandbox = self.sandbox_manager.create_sandbox(automation_id, agents, constraints)
        logger.info(f"   Sandbox ready: {sandbox['id']}")
        
        # 6. Save configuration
        configuration = {
            'automation_id': automation_id,
            'request': request,
            'domain': domain,
            'info': info,
            'regulations': regulations,
            'constraints': constraints,
            'agents': agents,
            'sandbox': sandbox,
            'created_at': datetime.now().isoformat(),
            'phase': 'setup_complete'
        }
        
        logger.info("=" * 60)
        logger.info("PHASE 1 COMPLETE - Automation Ready")
        logger.info("=" * 60)
        
        return configuration

# ============================================================================
# PHASE 2: PRODUCTION EXECUTION
# ============================================================================

class ProductionExecutionOrchestrator:
    """Phase 2: Orchestrates production execution.

    Attributes:
        configurations: Saved automation configurations keyed by automation_id.
        execution_history: List of deliverable dicts per automation_id.
        learned_patterns: Per-automation learning state.  Each entry is a dict
            with keys ``total_runs``, ``success_count``, ``failure_count``,
            ``failed_agents`` (agent_type → failure count), ``avg_steps``
            (running average of steps per execution), and ``last_status``.
    """
    def __init__(self):
        self.configurations: Dict[str, Dict[str, Any]] = {}
        self.execution_history: Dict[str, List[Dict[str, Any]]] = {}
        self.learned_patterns: Dict[str, Dict[str, Any]] = {}
        
    def save_configuration(self, config: Dict[str, Any]):
        """Save automation configuration"""
        automation_id = config['automation_id']
        self.configurations[automation_id] = config
        logger.info(f"Configuration saved: {automation_id}")
        
    def load_configuration(self, automation_id: str) -> Optional[Dict[str, Any]]:
        """Load automation configuration"""
        return self.configurations.get(automation_id)
        
    def execute_phase2(self, automation_id: str) -> Dict[str, Any]:
        """
        Execute Phase 2: Production Execution
        """
        logger.info("=" * 60)
        logger.info("PHASE 2: PRODUCTION EXECUTION")
        logger.info("=" * 60)
        
        # 1. Load configuration
        logger.info(f"1. Loading configuration for {automation_id}...")
        config = self.load_configuration(automation_id)
        if not config:
            return {'error': 'Configuration not found'}
        logger.info(f"   Loaded: {len(config['agents'])} agents")
        
        # 2. Execute workflow
        logger.info("2. Executing workflow...")
        results = self._execute_workflow(config)
        logger.info(f"   Execution: {results['status']}")
        
        # 3. Produce deliverables
        logger.info("3. Producing deliverables...")
        deliverables = self._create_deliverables(config, results)
        logger.info(f"   Deliverables: {len(deliverables)} items")
        
        # 4. Store results
        logger.info("4. Storing results...")
        self._store_results(automation_id, deliverables)
        
        # 5. Learn from execution
        logger.info("5. Learning from execution...")
        self._learn_from_execution(automation_id, results)
        
        logger.info("=" * 60)
        logger.info("PHASE 2 COMPLETE - Deliverables Produced")
        logger.info("=" * 60)
        
        return {
            'automation_id': automation_id,
            'execution_time': datetime.now().isoformat(),
            'results': results,
            'deliverables': deliverables
        }
        
    def _execute_workflow(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the workflow with configured agents"""
        results = {
            'status': 'success',
            'steps': []
        }
        
        for agent in config['agents']:
            step_result = {
                'agent': agent['type'],
                'role': agent['role'],
                'status': 'success',
                'output': f"Executed {agent['role']}"
            }
            results['steps'].append(step_result)
            
        return results
        
    def _create_deliverables(self, config: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
        """Create deliverables from execution results"""
        return {
            'urls': ['https://example.com/post-1', 'https://medium.com/@user/post-1'],
            'files': [],
            'reports': {'execution_summary': results},
            'timestamp': datetime.now().isoformat()
        }
        
    def _store_results(self, automation_id: str, deliverables: Dict[str, Any]):
        """Store execution results"""
        if automation_id not in self.execution_history:
            self.execution_history[automation_id] = []
        self.execution_history[automation_id].append(deliverables)
        
    def _learn_from_execution(self, automation_id: str, results: Dict[str, Any]):
        """Learn from execution to improve future runs.

        Analyses the execution *results* for the given *automation_id* and
        records patterns that can be used to optimise subsequent executions:

        * **Success rate** — tracked per-automation so that consistently
          failing automations can be flagged for human review.
        * **Failure patterns** — if specific agent steps failed, the failure
          reasons are recorded so the system can skip or adapt those steps.
        * **Performance metrics** — step durations are aggregated (when
          available) to identify bottlenecks.
        """
        history = self.execution_history.get(automation_id, [])
        patterns = self.learned_patterns.setdefault(automation_id, {
            'total_runs': 0,
            'success_count': 0,
            'failure_count': 0,
            'failed_agents': {},
            'avg_steps': 0.0,
            'last_status': 'unknown',
        })

        patterns['total_runs'] += 1
        overall_status = results.get('status', 'unknown')
        patterns['last_status'] = overall_status

        if overall_status == 'success':
            patterns['success_count'] += 1
        else:
            patterns['failure_count'] += 1

        # Analyse individual steps for failure signals.
        steps = results.get('steps', [])
        for step in steps:
            if step.get('status') != 'success':
                agent_type = step.get('agent', 'unknown')
                agent_failures = patterns['failed_agents'].setdefault(agent_type, 0)
                patterns['failed_agents'][agent_type] = agent_failures + 1

        # Running average of step count (proxy for complexity tracking).
        n = patterns['total_runs']
        patterns['avg_steps'] = (
            (patterns['avg_steps'] * (n - 1) + len(steps)) / n
        )

        logger.info(
            "Learned from execution %s: status=%s, runs=%d, success_rate=%.1f%%",
            automation_id,
            overall_status,
            n,
            (patterns['success_count'] / n) * 100 if n else 0,
        )

# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

class TwoPhaseOrchestrator:
    """
    Main orchestrator for two-phase execution
    """
    def __init__(self):
        self.phase1 = GenerativeSetupOrchestrator()
        self.phase2 = ProductionExecutionOrchestrator()
        
    def create_automation(self, request: str, domain: str) -> str:
        """
        Phase 1: Create automation (generative setup)
        Returns automation_id
        """
        config = self.phase1.execute_phase1(request, domain)
        self.phase2.save_configuration(config)
        return config['automation_id']
        
    def run_automation(self, automation_id: str) -> Dict[str, Any]:
        """
        Phase 2: Run automation (production execution)
        Returns deliverables
        """
        return self.phase2.execute_phase2(automation_id)
        
    def get_automation_config(self, automation_id: str) -> Optional[Dict[str, Any]]:
        """Get automation configuration"""
        return self.phase2.load_configuration(automation_id)
        
    def get_execution_history(self, automation_id: str) -> List[Dict[str, Any]]:
        """Get execution history"""
        return self.phase2.execution_history.get(automation_id, [])

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Create orchestrator
    orchestrator = TwoPhaseOrchestrator()
    
    # Phase 1: Create automation
    print("\n" + "=" * 80)
    print("CREATING AUTOMATION")
    print("=" * 80)
    automation_id = orchestrator.create_automation(
        request="Automate my blog publishing to WordPress and Medium with approval",
        domain="publishing"
    )
    print(f"\nAutomation created: {automation_id}")
    
    # Phase 2: Run automation
    print("\n" + "=" * 80)
    print("RUNNING AUTOMATION")
    print("=" * 80)
    result = orchestrator.run_automation(automation_id)
    print(f"\nDeliverables produced:")
    print(json.dumps(result['deliverables'], indent=2))
    
    # Run again (automated repeat)
    print("\n" + "=" * 80)
    print("RUNNING AUTOMATION AGAIN (Automated Repeat)")
    print("=" * 80)
    result2 = orchestrator.run_automation(automation_id)
    print(f"\nDeliverables produced:")
    print(json.dumps(result2['deliverables'], indent=2))