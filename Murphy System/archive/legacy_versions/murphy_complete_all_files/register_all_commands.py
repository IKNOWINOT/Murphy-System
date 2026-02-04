"""
Murphy System - Comprehensive Command Registration
Registers ALL commands from ALL integrated systems
"""

from command_system import CommandRegistry, Command, CommandCategory
import logging

logger = logging.getLogger(__name__)


def register_llm_commands(registry: CommandRegistry):
    """Register LLM system commands"""
    commands = [
        Command(
            name="llm.generate",
            description="Generate text using LLM",
            category=CommandCategory.SYSTEM,
            module="llm",
            parameters=[
                {"name": "prompt", "description": "Text prompt", "required": True},
                {"name": "model", "description": "Model to use", "required": False},
                {"name": "max_tokens", "description": "Max tokens", "required": False}
            ],
            examples=["/llm.generate Write a story about AI"]
        ),
        Command(
            name="llm.chat",
            description="Chat with LLM",
            category=CommandCategory.SYSTEM,
            module="llm",
            parameters=[
                {"name": "message", "description": "Chat message", "required": True}
            ],
            examples=["/llm.chat Hello, how are you?"]
        ),
        Command(
            name="llm.models",
            description="List available LLM models",
            category=CommandCategory.SYSTEM,
            module="llm",
            examples=["/llm.models"]
        ),
        Command(
            name="llm.stats",
            description="Show LLM usage statistics",
            category=CommandCategory.SYSTEM,
            module="llm",
            examples=["/llm.stats"]
        )
    ]
    
    for cmd in commands:
        registry.register_command(cmd)
    
    logger.info(f"✓ Registered {len(commands)} LLM commands")


def register_librarian_commands(registry: CommandRegistry):
    """Register Librarian system commands"""
    commands = [
        Command(
            name="librarian.store",
            description="Store knowledge in Librarian",
            category=CommandCategory.LIBRARIAN,
            module="librarian",
            parameters=[
                {"name": "content", "description": "Content to store", "required": True},
                {"name": "tags", "description": "Tags (comma-separated)", "required": False}
            ],
            examples=["/librarian.store This is important knowledge"]
        ),
        Command(
            name="librarian.search",
            description="Search Librarian knowledge base",
            category=CommandCategory.LIBRARIAN,
            module="librarian",
            parameters=[
                {"name": "query", "description": "Search query", "required": True},
                {"name": "limit", "description": "Max results", "required": False}
            ],
            examples=["/librarian.search AI automation"]
        ),
        Command(
            name="librarian.recall",
            description="Recall specific knowledge by ID",
            category=CommandCategory.LIBRARIAN,
            module="librarian",
            parameters=[
                {"name": "id", "description": "Knowledge ID", "required": True}
            ],
            examples=["/librarian.recall 12345"]
        ),
        Command(
            name="librarian.stats",
            description="Show Librarian statistics",
            category=CommandCategory.LIBRARIAN,
            module="librarian",
            examples=["/librarian.stats"]
        ),
        Command(
            name="librarian.export",
            description="Export knowledge base",
            category=CommandCategory.LIBRARIAN,
            module="librarian",
            parameters=[
                {"name": "format", "description": "Export format (json/csv)", "required": False}
            ],
            examples=["/librarian.export json"]
        )
    ]
    
    for cmd in commands:
        registry.register_command(cmd)
    
    logger.info(f"✓ Registered {len(commands)} Librarian commands")


def register_monitoring_commands(registry: CommandRegistry):
    """Register Monitoring system commands"""
    commands = [
        Command(
            name="monitor.health",
            description="Check system health",
            category=CommandCategory.MONITORING,
            module="monitoring",
            examples=["/monitor.health"]
        ),
        Command(
            name="monitor.metrics",
            description="View system metrics",
            category=CommandCategory.MONITORING,
            module="monitoring",
            parameters=[
                {"name": "component", "description": "Specific component", "required": False}
            ],
            examples=["/monitor.metrics", "/monitor.metrics llm"]
        ),
        Command(
            name="monitor.alerts",
            description="View active alerts",
            category=CommandCategory.MONITORING,
            module="monitoring",
            examples=["/monitor.alerts"]
        ),
        Command(
            name="monitor.anomalies",
            description="Detect anomalies",
            category=CommandCategory.MONITORING,
            module="monitoring",
            examples=["/monitor.anomalies"]
        ),
        Command(
            name="monitor.logs",
            description="View system logs",
            category=CommandCategory.MONITORING,
            module="monitoring",
            parameters=[
                {"name": "level", "description": "Log level", "required": False},
                {"name": "limit", "description": "Max entries", "required": False}
            ],
            examples=["/monitor.logs", "/monitor.logs ERROR 50"]
        ),
        Command(
            name="monitor.performance",
            description="View performance metrics",
            category=CommandCategory.MONITORING,
            module="monitoring",
            examples=["/monitor.performance"]
        )
    ]
    
    for cmd in commands:
        registry.register_command(cmd)
    
    logger.info(f"✓ Registered {len(commands)} Monitoring commands")


def register_artifact_commands(registry: CommandRegistry):
    """Register Artifact system commands"""
    commands = [
        Command(
            name="artifact.create",
            description="Create new artifact",
            category=CommandCategory.ARTIFACT,
            module="artifacts",
            parameters=[
                {"name": "type", "description": "Artifact type", "required": True},
                {"name": "content", "description": "Artifact content", "required": True}
            ],
            examples=["/artifact.create document My document content"]
        ),
        Command(
            name="artifact.list",
            description="List all artifacts",
            category=CommandCategory.ARTIFACT,
            module="artifacts",
            parameters=[
                {"name": "type", "description": "Filter by type", "required": False}
            ],
            examples=["/artifact.list", "/artifact.list document"]
        ),
        Command(
            name="artifact.view",
            description="View artifact details",
            category=CommandCategory.ARTIFACT,
            module="artifacts",
            parameters=[
                {"name": "id", "description": "Artifact ID", "required": True}
            ],
            examples=["/artifact.view 12345"]
        ),
        Command(
            name="artifact.update",
            description="Update artifact",
            category=CommandCategory.ARTIFACT,
            module="artifacts",
            parameters=[
                {"name": "id", "description": "Artifact ID", "required": True},
                {"name": "content", "description": "New content", "required": True}
            ],
            examples=["/artifact.update 12345 Updated content"]
        ),
        Command(
            name="artifact.delete",
            description="Delete artifact",
            category=CommandCategory.ARTIFACT,
            module="artifacts",
            parameters=[
                {"name": "id", "description": "Artifact ID", "required": True}
            ],
            examples=["/artifact.delete 12345"],
            risk_level="HIGH"
        ),
        Command(
            name="artifact.search",
            description="Search artifacts",
            category=CommandCategory.ARTIFACT,
            module="artifacts",
            parameters=[
                {"name": "query", "description": "Search query", "required": True}
            ],
            examples=["/artifact.search automation"]
        ),
        Command(
            name="artifact.export",
            description="Export artifact",
            category=CommandCategory.ARTIFACT,
            module="artifacts",
            parameters=[
                {"name": "id", "description": "Artifact ID", "required": True},
                {"name": "format", "description": "Export format", "required": False}
            ],
            examples=["/artifact.export 12345 pdf"]
        )
    ]
    
    for cmd in commands:
        registry.register_command(cmd)
    
    logger.info(f"✓ Registered {len(commands)} Artifact commands")


def register_shadow_agent_commands(registry: CommandRegistry):
    """Register Shadow Agent system commands"""
    commands = [
        Command(
            name="shadow.observe",
            description="Start observing user actions",
            category=CommandCategory.SHADOW,
            module="shadow_agents",
            examples=["/shadow.observe"]
        ),
        Command(
            name="shadow.learn",
            description="Learn from observations",
            category=CommandCategory.SHADOW,
            module="shadow_agents",
            examples=["/shadow.learn"]
        ),
        Command(
            name="shadow.propose",
            description="Propose automation",
            category=CommandCategory.SHADOW,
            module="shadow_agents",
            parameters=[
                {"name": "pattern", "description": "Pattern to automate", "required": True}
            ],
            examples=["/shadow.propose daily report generation"]
        ),
        Command(
            name="shadow.approve",
            description="Approve automation proposal",
            category=CommandCategory.SHADOW,
            module="shadow_agents",
            parameters=[
                {"name": "id", "description": "Proposal ID", "required": True}
            ],
            examples=["/shadow.approve 12345"],
            risk_level="MEDIUM"
        ),
        Command(
            name="shadow.reject",
            description="Reject automation proposal",
            category=CommandCategory.SHADOW,
            module="shadow_agents",
            parameters=[
                {"name": "id", "description": "Proposal ID", "required": True}
            ],
            examples=["/shadow.reject 12345"]
        ),
        Command(
            name="shadow.automations",
            description="List active automations",
            category=CommandCategory.SHADOW,
            module="shadow_agents",
            examples=["/shadow.automations"]
        ),
        Command(
            name="shadow.stats",
            description="Show shadow agent statistics",
            category=CommandCategory.SHADOW,
            module="shadow_agents",
            examples=["/shadow.stats"]
        )
    ]
    
    for cmd in commands:
        registry.register_command(cmd)
    
    logger.info(f"✓ Registered {len(commands)} Shadow Agent commands")


def register_swarm_commands(registry: CommandRegistry):
    """Register Cooperative Swarm commands"""
    commands = [
        Command(
            name="swarm.create",
            description="Create agent swarm",
            category=CommandCategory.COOPERATIVE,
            module="swarm",
            parameters=[
                {"name": "agents", "description": "Agent types (comma-separated)", "required": True},
                {"name": "goal", "description": "Swarm goal", "required": True}
            ],
            examples=["/swarm.create researcher,writer,reviewer Write a research paper"]
        ),
        Command(
            name="swarm.list",
            description="List active swarms",
            category=CommandCategory.COOPERATIVE,
            module="swarm",
            examples=["/swarm.list"]
        ),
        Command(
            name="swarm.status",
            description="Check swarm status",
            category=CommandCategory.COOPERATIVE,
            module="swarm",
            parameters=[
                {"name": "id", "description": "Swarm ID", "required": True}
            ],
            examples=["/swarm.status 12345"]
        ),
        Command(
            name="swarm.stop",
            description="Stop swarm execution",
            category=CommandCategory.COOPERATIVE,
            module="swarm",
            parameters=[
                {"name": "id", "description": "Swarm ID", "required": True}
            ],
            examples=["/swarm.stop 12345"],
            risk_level="MEDIUM"
        ),
        Command(
            name="swarm.agents",
            description="List available agent types",
            category=CommandCategory.COOPERATIVE,
            module="swarm",
            examples=["/swarm.agents"]
        )
    ]
    
    for cmd in commands:
        registry.register_command(cmd)
    
    logger.info(f"✓ Registered {len(commands)} Swarm commands")


def register_workflow_commands(registry: CommandRegistry):
    """Register Workflow Orchestrator commands"""
    commands = [
        Command(
            name="workflow.create",
            description="Create new workflow",
            category=CommandCategory.SYSTEM,
            module="workflow",
            parameters=[
                {"name": "name", "description": "Workflow name", "required": True},
                {"name": "steps", "description": "Workflow steps (JSON)", "required": True}
            ],
            examples=["/workflow.create MyWorkflow {...}"]
        ),
        Command(
            name="workflow.list",
            description="List all workflows",
            category=CommandCategory.SYSTEM,
            module="workflow",
            examples=["/workflow.list"]
        ),
        Command(
            name="workflow.execute",
            description="Execute workflow",
            category=CommandCategory.SYSTEM,
            module="workflow",
            parameters=[
                {"name": "id", "description": "Workflow ID", "required": True},
                {"name": "params", "description": "Execution parameters", "required": False}
            ],
            examples=["/workflow.execute 12345"],
            risk_level="MEDIUM"
        ),
        Command(
            name="workflow.status",
            description="Check workflow execution status",
            category=CommandCategory.SYSTEM,
            module="workflow",
            parameters=[
                {"name": "execution_id", "description": "Execution ID", "required": True}
            ],
            examples=["/workflow.status exec-12345"]
        ),
        Command(
            name="workflow.stop",
            description="Stop workflow execution",
            category=CommandCategory.SYSTEM,
            module="workflow",
            parameters=[
                {"name": "execution_id", "description": "Execution ID", "required": True}
            ],
            examples=["/workflow.stop exec-12345"],
            risk_level="HIGH"
        ),
        Command(
            name="workflow.delete",
            description="Delete workflow",
            category=CommandCategory.SYSTEM,
            module="workflow",
            parameters=[
                {"name": "id", "description": "Workflow ID", "required": True}
            ],
            examples=["/workflow.delete 12345"],
            risk_level="HIGH"
        )
    ]
    
    for cmd in commands:
        registry.register_command(cmd)
    
    logger.info(f"✓ Registered {len(commands)} Workflow commands")


def register_learning_commands(registry: CommandRegistry):
    """Register Learning Engine commands"""
    commands = [
        Command(
            name="learn.patterns",
            description="View learned patterns",
            category=CommandCategory.SYSTEM,
            module="learning",
            examples=["/learn.patterns"]
        ),
        Command(
            name="learn.optimize",
            description="Optimize system based on learning",
            category=CommandCategory.SYSTEM,
            module="learning",
            examples=["/learn.optimize"],
            risk_level="MEDIUM"
        ),
        Command(
            name="learn.feedback",
            description="Provide feedback for learning",
            category=CommandCategory.SYSTEM,
            module="learning",
            parameters=[
                {"name": "action", "description": "Action that was performed", "required": True},
                {"name": "rating", "description": "Rating (1-5)", "required": True}
            ],
            examples=["/learn.feedback generate_report 5"]
        ),
        Command(
            name="learn.stats",
            description="Show learning statistics",
            category=CommandCategory.SYSTEM,
            module="learning",
            examples=["/learn.stats"]
        )
    ]
    
    for cmd in commands:
        registry.register_command(cmd)
    
    logger.info(f"✓ Registered {len(commands)} Learning commands")


def register_database_commands(registry: CommandRegistry):
    """Register Database commands"""
    commands = [
        Command(
            name="db.query",
            description="Execute database query",
            category=CommandCategory.SYSTEM,
            module="database",
            parameters=[
                {"name": "sql", "description": "SQL query", "required": True}
            ],
            examples=["/db.query SELECT * FROM tasks LIMIT 10"],
            risk_level="HIGH"
        ),
        Command(
            name="db.tables",
            description="List database tables",
            category=CommandCategory.SYSTEM,
            module="database",
            examples=["/db.tables"]
        ),
        Command(
            name="db.schema",
            description="View table schema",
            category=CommandCategory.SYSTEM,
            module="database",
            parameters=[
                {"name": "table", "description": "Table name", "required": True}
            ],
            examples=["/db.schema tasks"]
        ),
        Command(
            name="db.backup",
            description="Create database backup",
            category=CommandCategory.SYSTEM,
            module="database",
            examples=["/db.backup"],
            risk_level="MEDIUM"
        ),
        Command(
            name="db.stats",
            description="Show database statistics",
            category=CommandCategory.SYSTEM,
            module="database",
            examples=["/db.stats"]
        )
    ]
    
    for cmd in commands:
        registry.register_command(cmd)
    
    logger.info(f"✓ Registered {len(commands)} Database commands")


def register_business_commands(registry: CommandRegistry):
    """Register Business Automation commands"""
    commands = [
        Command(
            name="business.product.create",
            description="Create autonomous product",
            category=CommandCategory.SYSTEM,
            module="business",
            parameters=[
                {"name": "type", "description": "Product type", "required": True},
                {"name": "topic", "description": "Product topic", "required": True},
                {"name": "price", "description": "Product price", "required": True}
            ],
            examples=["/business.product.create textbook AI Automation 29.99"],
            risk_level="MEDIUM"
        ),
        Command(
            name="business.products",
            description="List all products",
            category=CommandCategory.SYSTEM,
            module="business",
            examples=["/business.products"]
        ),
        Command(
            name="business.sales",
            description="View sales statistics",
            category=CommandCategory.SYSTEM,
            module="business",
            examples=["/business.sales"]
        ),
        Command(
            name="business.customers",
            description="List customers",
            category=CommandCategory.SYSTEM,
            module="business",
            examples=["/business.customers"]
        ),
        Command(
            name="business.marketing.campaign",
            description="Create marketing campaign",
            category=CommandCategory.SYSTEM,
            module="business",
            parameters=[
                {"name": "product_id", "description": "Product ID", "required": True},
                {"name": "channels", "description": "Marketing channels", "required": True}
            ],
            examples=["/business.marketing.campaign 12345 email,social"],
            risk_level="MEDIUM"
        ),
        Command(
            name="business.payment.setup",
            description="Setup payment processing (PayPal, Square, Coinbase, Paddle, LemonSqueezy)",
            category=CommandCategory.SYSTEM,
            module="business",
            parameters=[
                {"name": "provider", "description": "Payment provider: paypal, square, coinbase, paddle, lemonsqueezy", "required": True}
            ],
            examples=[
                "/business.payment.setup paypal",
                "/business.payment.setup square",
                "/business.payment.setup coinbase"
            ],
            risk_level="HIGH"
        ),
        Command(
            name="business.payment.providers",
            description="List supported payment providers",
            category=CommandCategory.SYSTEM,
            module="business",
            examples=["/business.payment.providers"]
        )
    ]
    
    for cmd in commands:
        registry.register_command(cmd)
    
    logger.info(f"✓ Registered {len(commands)} Business commands")


def register_production_commands(registry: CommandRegistry):
    """Register Production Readiness commands"""
    commands = [
        Command(
            name="prod.readiness",
            description="Check production readiness",
            category=CommandCategory.SYSTEM,
            module="production",
            examples=["/prod.readiness"]
        ),
        Command(
            name="prod.setup",
            description="Run production setup",
            category=CommandCategory.SYSTEM,
            module="production",
            examples=["/prod.setup"],
            risk_level="CRITICAL"
        ),
        Command(
            name="prod.ssl.status",
            description="Check SSL certificate status",
            category=CommandCategory.SYSTEM,
            module="production",
            examples=["/prod.ssl.status"]
        ),
        Command(
            name="prod.ssl.setup",
            description="Setup SSL certificates",
            category=CommandCategory.SYSTEM,
            module="production",
            parameters=[
                {"name": "domain", "description": "Domain name", "required": True}
            ],
            examples=["/prod.ssl.setup example.com"],
            risk_level="HIGH"
        ),
        Command(
            name="prod.schema.migrate",
            description="Run database migrations",
            category=CommandCategory.SYSTEM,
            module="production",
            examples=["/prod.schema.migrate"],
            risk_level="CRITICAL"
        )
    ]
    
    for cmd in commands:
        registry.register_command(cmd)
    
    logger.info(f"✓ Registered {len(commands)} Production commands")


def register_all_system_commands(registry: CommandRegistry):
    """Register ALL commands from ALL systems"""
    
    logger.info("=" * 60)
    logger.info("Registering ALL Murphy System Commands")
    logger.info("=" * 60)
    
    # Register commands from each system
    register_llm_commands(registry)
    register_librarian_commands(registry)
    register_monitoring_commands(registry)
    register_artifact_commands(registry)
    register_shadow_agent_commands(registry)
    register_swarm_commands(registry)
    register_workflow_commands(registry)
    register_learning_commands(registry)
    register_database_commands(registry)
    register_business_commands(registry)
    register_production_commands(registry)
    
    total_commands = len(registry.get_all_commands())
    
    logger.info("=" * 60)
    logger.info(f"✓ Total Commands Registered: {total_commands}")
    logger.info("=" * 60)
    
    return total_commands


def get_command_summary(registry: CommandRegistry) -> dict:
    """Get summary of all registered commands"""
    
    all_commands = registry.get_all_commands()
    
    by_module = {}
    by_category = {}
    
    for cmd in all_commands:
        # By module
        module = cmd.module or "core"
        if module not in by_module:
            by_module[module] = []
        by_module[module].append(cmd.name)
        
        # By category
        category = cmd.category.value
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(cmd.name)
    
    return {
        "total": len(all_commands),
        "by_module": {k: len(v) for k, v in by_module.items()},
        "by_category": {k: len(v) for k, v in by_category.items()},
        "modules": sorted(by_module.keys()),
        "categories": sorted(by_category.keys())
    }