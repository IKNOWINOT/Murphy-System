# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Hybrid Command/Natural Language System

This system provides:
- Command interpretation dropdown
- Natural language to command translation
- Command to natural language reverse translation
- Workflow command generation
- Interactive command editing
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """Types of commands"""
    SWARM = "swarm"
    ANALYZE = "analyze"
    PLAN = "plan"
    CAMPAIGN = "campaign"
    CONTENT = "content"
    LEAD = "lead"
    PROPOSAL = "proposal"
    BUDGET = "budget"
    DEPLOY = "deploy"
    TEST = "test"
    APPROVE = "approve"


@dataclass
class HybridCommand:
    """A hybrid command with both command and natural language"""
    command: str
    natural_language: str
    bot_role: str
    domain: str
    action: str
    args: str
    comment: str
    confidence: float = 1.0


@dataclass
class CommandInterpretation:
    """Interpretation of a command in natural language"""
    original_command: str
    natural_language: str
    bot_role: str
    domain: str
    explanation: str
    example_usage: str
    related_commands: List[str]


@dataclass
class WorkflowCommandSequence:
    """A sequence of commands forming a workflow"""
    workflow_name: str
    description: str
    commands: List[str]  # Hybrid format: comma-separated, # for comments
    bot_sequence: List[str]
    expected_outcomes: List[str]


class HybridCommandSystem:
    """
    System for working with hybrid command/natural language
    
    Commands use format: /action args #comment
    Multiple commands separated by commas
    # is used for context/comments
    """
    
    def __init__(self, librarian_system=None, executive_bots=None):
        self.librarian = librarian_system
        self.executive_bots = executive_bots
        self.command_history: List[HybridCommand] = []
        self.workflow_templates: Dict[str, WorkflowCommandSequence] = {}
        
        self._initialize_workflow_templates()
        logger.info("Hybrid Command System initialized")
    
    def _initialize_workflow_templates(self):
        """Initialize workflow templates"""
        
        # Executive Planning Workflow
        self.workflow_templates["executive_planning"] = WorkflowCommandSequence(
            workflow_name="Executive Planning",
            description="Quarterly business planning by executive team",
            commands=[
                "/plan strategy #quarterly business objectives, /plan architecture #technical roadmap, /budget plan #resource allocation, /approve executive #final plan"
            ],
            bot_sequence=["CEO", "CTO", "CFO", "CEO"],
            expected_outcomes=[
                "Business strategy document",
                "Technical architecture plan",
                "Budget allocation",
                "Executive approval"
            ]
        )
        
        # Sales Pipeline Workflow
        self.workflow_templates["sales_pipeline"] = WorkflowCommandSequence(
            workflow_name="Sales Pipeline",
            description="Lead to closed deal automation",
            commands=[
                "/lead qualify #enterprise prospect, /proposal generate #custom solution, /review pricing #deal terms, /contract create #master agreement, /approve sales #final deal"
            ],
            bot_sequence=["Account Executive", "VP Sales", "CFO", "Account Executive"],
            expected_outcomes=[
                "Qualified lead",
                "Custom proposal",
                "Approved pricing",
                "Signed contract"
            ]
        )
        
        # Marketing Campaign Workflow
        self.workflow_templates["marketing_campaign"] = WorkflowCommandSequence(
            workflow_name="Marketing Campaign",
            description="Campaign planning and execution",
            commands=[
                "/campaign plan #Q4 launch, /content create #marketing materials, /analyze metrics #target audience, /budget allocate #campaign spend, /approve marketing #go live"
            ],
            bot_sequence=["VP Marketing", "Content Manager", "VP Marketing", "CFO", "VP Marketing"],
            expected_outcomes=[
                "Campaign strategy",
                "Marketing content",
                "Target audience analysis",
                "Approved budget",
                "Live campaign"
            ]
        )
        
        # Software Development Workflow
        self.workflow_templates["software_development"] = WorkflowCommandSequence(
            workflow_name="Software Development",
            description="Feature development and deployment",
            commands=[
                "/swarm generate SoftwareEngineer #implement feature, /analyze code #security review, /test automated #QA suite, /deploy staging #feature test, /approve technical #production release"
            ],
            bot_sequence=["VP Engineering", "Software Engineer", "QA Engineer", "VP Engineering", "CTO"],
            expected_outcomes=[
                "Implemented feature",
                "Security review passed",
                "Tests passing",
                "Staging deployment",
                "Production release"
            ]
        )
    
    def parse_hybrid_command(self, command: str) -> HybridCommand:
        """
        Parse a hybrid command
        
        Format: /action args #comment
        Multiple commands separated by commas
        """
        # Split by comma to get individual commands
        command_parts = [cmd.strip() for cmd in command.split(",")]
        
        # For now, parse the first command (single command mode)
        primary_cmd = command_parts[0]
        
        # Parse components
        parts = primary_cmd.split()
        
        if not parts:
            raise ValueError("Invalid command format")
        
        action = parts[0].replace("/", "").strip()
        
        # Find comment
        comment = ""
        args = ""
        comment_idx = -1
        for i, part in enumerate(parts):
            if part.startswith("#"):
                comment_idx = i
                comment = " ".join(parts[i:])[1:].strip()
                break
        
        # Get args
        if comment_idx > 1:
            args = " ".join(parts[1:comment_idx])
        elif comment_idx == -1 and len(parts) > 1:
            args = " ".join(parts[1:])
        
        # Determine bot and domain
        bot_role, domain = self._determine_bot_and_domain(action, args)
        
        # Generate natural language
        natural_language = self._command_to_natural(action, args, comment, bot_role)
        
        hybrid = HybridCommand(
            command=primary_cmd,
            natural_language=natural_language,
            bot_role=bot_role,
            domain=domain,
            action=action,
            args=args,
            comment=comment
        )
        
        self.command_history.append(hybrid)
        return hybrid
    
    def _determine_bot_and_domain(self, action: str, args: str) -> Tuple[str, str]:
        """Determine which bot and domain a command belongs to"""
        
        action_lower = action.lower()
        args_lower = args.lower()
        
        # Map actions to bots/domains
        if action_lower in ["swarm"]:
            # Look for bot role in args
            if "engineer" in args_lower:
                return "Software Engineer", "engineering"
            elif "marketing" in args_lower:
                return "VP Marketing", "marketing"
            elif "sales" in args_lower:
                return "Account Executive", "sales"
            else:
                return "Software Engineer", "engineering"
        
        elif action_lower in ["plan"]:
            if "strategy" in args_lower or "business" in args_lower:
                return "CEO", "executive"
            elif "architecture" in args_lower or "technical" in args_lower:
                return "CTO", "technology"
            else:
                return "CEO", "executive"
        
        elif action_lower in ["budget"]:
            return "CFO", "finance"
        
        elif action_lower in ["campaign"]:
            return "VP Marketing", "marketing"
        
        elif action_lower in ["content"]:
            return "Content Manager", "marketing"
        
        elif action_lower in ["lead", "proposal"]:
            return "Account Executive", "sales"
        
        elif action_lower in ["analyze"]:
            if "code" in args_lower:
                return "Software Engineer", "engineering"
            elif "metrics" in args_lower:
                return "VP Marketing", "marketing"
            else:
                return "Software Engineer", "engineering"
        
        elif action_lower in ["deploy"]:
            return "Software Engineer", "engineering"
        
        elif action_lower in ["test"]:
            return "QA Engineer", "engineering"
        
        elif action_lower in ["approve"]:
            return "CEO", "executive"
        
        else:
            return "Software Engineer", "engineering"
    
    def _command_to_natural(self, action: str, args: str, comment: str, bot_role: str) -> str:
        """Convert command to natural language"""
        
        action_templates = {
            "swarm": f"{bot_role} should generate a swarm of AI agents to {comment if comment else args}",
            "analyze": f"{bot_role} should analyze {args if args else 'the target'} with focus on {comment if comment else 'detailed review'}",
            "plan": f"{bot_role} should create a plan for {args if args else 'the objective'} considering {comment if comment else 'strategic approach'}",
            "campaign": f"{bot_role} should launch a marketing campaign {args if args else 'as specified'} with goal: {comment if comment else 'brand awareness'}",
            "content": f"{bot_role} should create content about {args if args else 'the topic'} with context: {comment if comment else 'brand guidelines'}",
            "lead": f"{bot_role} should manage lead {args if args else 'prospect'} with details: {comment if comment else 'qualification criteria'}",
            "proposal": f"{bot_role} should generate a proposal for {args if args else 'the opportunity'} covering: {comment if comment else 'solution overview'}",
            "budget": f"{bot_role} should create or manage budget {args if args else 'allocation'} for: {comment if comment else 'operational expenses'}",
            "deploy": f"{bot_role} should deploy {args if args else 'the system'} to environment: {comment if comment else 'production'}",
            "test": f"{bot_role} should run tests on {args if args else 'the code'} with focus on: {comment if comment else 'quality assurance'}",
            "approve": f"{bot_role} should approve {args if args else 'the request'} based on: {comment if comment else 'established criteria'}"
        }
        
        return action_templates.get(action, f"{bot_role} should execute {action} on {args} with context: {comment}")
    
    def natural_to_command(self, natural: str) -> HybridCommand:
        """Convert natural language to hybrid command"""
        
        # Use librarian if available
        if self.librarian:
            try:
                result = self.librarian.natural_to_command(natural)
                if result.get("type") == "command":
                    return self.parse_hybrid_command(result["command"])
            except Exception as e:
                logger.error(f"Librarian conversion failed: {e}")
        
        # Fallback: rule-based conversion
        return self._rule_based_conversion(natural)
    
    def _rule_based_conversion(self, natural: str) -> HybridCommand:
        """Rule-based natural language to command conversion"""
        natural_lower = natural.lower()
        
        # Detect intent and extract components
        action = None
        args = ""
        comment = natural
        
        # Swarm generation
        if any(word in natural_lower for word in ["swarm", "team", "agents", "generate"]):
            action = "swarm"
            
            # Extract bot role
            if "engineer" in natural_lower:
                args = "SoftwareEngineer"
            elif "marketing" in natural_lower:
                args = "MarketingTeam"
            elif "sales" in natural_lower:
                args = "SalesTeam"
            else:
                args = "Engineer"
        
        # Analysis
        elif "analyze" in natural_lower or "review" in natural_lower:
            action = "analyze"
            args = "target"
        
        # Planning
        elif "plan" in natural_lower or "strategy" in natural_lower:
            action = "plan"
            args = "objectives"
        
        # Campaign
        elif "campaign" in natural_lower or "launch" in natural_lower:
            action = "campaign"
            args = "Q4 initiative"
        
        # Content
        elif "content" in natural_lower or "create" in natural_lower:
            action = "content"
            args = "marketing materials"
        
        # Budget
        elif "budget" in natural_lower or "financial" in natural_lower:
            action = "budget"
            args = "allocation"
        
        # Deploy
        elif "deploy" in natural_lower or "release" in natural_lower:
            action = "deploy"
            args = "production"
        
        # Test
        elif "test" in natural_lower or "qa" in natural_lower:
            action = "test"
            args = "automated"
        
        # Approve
        elif "approve" in natural_lower or "authorize" in natural_lower:
            action = "approve"
            args = "request"
        
        else:
            # Default: use as comment
            action = "swarm"
            args = "Engineer"
            comment = natural
        
        # Construct command
        command = f"/{action} {args} #{comment}"
        
        return self.parse_hybrid_command(command)
    
    def interpret_command(self, command: str) -> CommandInterpretation:
        """
        Create a detailed interpretation of a command
        
        Returns natural language explanation, bot role, domain, etc.
        """
        try:
            hybrid = self.parse_hybrid_command(command)
            
            # Generate explanation
            explanation = self._generate_explanation(hybrid)
            
            # Generate example usage
            example_usage = self._generate_example(hybrid)
            
            # Find related commands
            related_commands = self._find_related_commands(hybrid)
            
            interpretation = CommandInterpretation(
                original_command=command,
                natural_language=hybrid.natural_language,
                bot_role=hybrid.bot_role,
                domain=hybrid.domain,
                explanation=explanation,
                example_usage=example_usage,
                related_commands=related_commands
            )
            
            return interpretation
        
        except Exception as e:
            logger.error(f"Command interpretation failed: {e}")
            return CommandInterpretation(
                original_command=command,
                natural_language="Unable to interpret",
                bot_role="Unknown",
                domain="Unknown",
                explanation=f"Error interpreting command: {str(e)}",
                example_usage="",
                related_commands=[]
            )
    
    def _generate_explanation(self, hybrid: HybridCommand) -> str:
        """Generate detailed explanation of command"""
        explanation = f"""
**Command:** {hybrid.command}
**Action:** {hybrid.action}
**Executed by:** {hybrid.bot_role}
**Domain:** {hybrid.domain}

**Natural Language:**
{hybrid.natural_language}

**What it does:**
This command instructs the {hybrid.bot_role} to perform the '{hybrid.action}' action.
"""
        
        if hybrid.args:
            explanation += f"\n**Arguments:** {hybrid.args}"
        
        if hybrid.comment:
            explanation += f"\n**Context:** {hybrid.comment}"
        
        return explanation
    
    def _generate_example(self, hybrid: HybridCommand) -> str:
        """Generate example usage of command"""
        return f"""
Example workflow execution:

1. {hybrid.bot_role} receives: {hybrid.command}
2. Parses action: {hybrid.action}
3. Understands context: {hybrid.comment}
4. Executes according to {hybrid.domain} domain best practices
5. Returns result with domain-specific terminology
"""
    
    def _find_related_commands(self, hybrid: HybridCommand) -> List[str]:
        """Find commands related to this one"""
        related = []
        
        # Same action, different context
        if hybrid.action == "swarm":
            related.extend([
                f"/swarm SeniorEngineer #{hybrid.comment}",
                f"/swarm MarketingTeam #{hybrid.comment}",
                f"/swarm SalesTeam #{hybrid.comment}"
            ])
        
        # Same domain, different actions
        if hybrid.domain == "engineering":
            related.extend([
                f"/analyze code #{hybrid.comment}",
                f"/test automated #{hybrid.comment}",
                f"/deploy staging #{hybrid.comment}"
            ])
        
        elif hybrid.domain == "marketing":
            related.extend([
                f"/campaign launch #{hybrid.comment}",
                f"/content create #{hybrid.comment}",
                f"/analyze metrics #{hybrid.comment}"
            ])
        
        elif hybrid.domain == "sales":
            related.extend([
                f"/lead qualify #{hybrid.comment}",
                f"/proposal generate #{hybrid.comment}",
                f"/contract create #{hybrid.comment}"
            ])
        
        return related[:5]  # Return top 5
    
    def generate_workflow_commands(self, workflow_name: str) -> Optional[WorkflowCommandSequence]:
        """Generate commands for a workflow"""
        return self.workflow_templates.get(workflow_name)
    
    def get_available_workflows(self) -> List[Dict[str, Any]]:
        """Get all available workflows"""
        return [
            {
                "name": workflow.workflow_name,
                "description": workflow.description,
                "bot_count": len(workflow.bot_sequence),
                "command_count": len(workflow.commands)
            }
            for workflow in self.workflow_templates.values()
        ]
    
    def validate_command_syntax(self, command: str) -> Dict[str, Any]:
        """Validate command syntax"""
        errors = []
        warnings = []
        
        # Check if command starts with /
        if not command.startswith("/"):
            errors.append("Command must start with /")
        
        # Check if action exists
        parts = command.split()
        if not parts:
            errors.append("No command action found")
        else:
            action = parts[0].replace("/", "").strip()
            valid_actions = [cmd.value for cmd in CommandType]
            if action not in valid_actions:
                warnings.append(f"Action '{action}' not in standard command types")
        
        # Check for comment separator
        if "#" not in command:
            warnings.append("No context/comment found. Consider adding #comment for clarity")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def get_command_dropdown_data(self) -> Dict[str, Any]:
        """
        Get data for command dropdown interface
        
        Returns structure for building interactive dropdown
        """
        return {
            "actions": [
                {
                    "name": "swarm",
                    "description": "Generate AI agent swarm",
                    "example": "/swarm Engineer #implement feature"
                },
                {
                    "name": "analyze",
                    "description": "Analyze target",
                    "example": "/analyze code #security review"
                },
                {
                    "name": "plan",
                    "description": "Create plan",
                    "example": "/plan strategy #quarterly objectives"
                },
                {
                    "name": "campaign",
                    "description": "Launch marketing campaign",
                    "example": "/campaign launch #Q4 initiative"
                },
                {
                    "name": "content",
                    "description": "Create content",
                    "example": "/content create #marketing materials"
                },
                {
                    "name": "lead",
                    "description": "Manage leads",
                    "example": "/lead qualify #prospect"
                },
                {
                    "name": "proposal",
                    "description": "Generate proposal",
                    "example": "/proposal generate #client solution"
                },
                {
                    "name": "budget",
                    "description": "Manage budget",
                    "example": "/budget plan #Q4 allocation"
                },
                {
                    "name": "deploy",
                    "description": "Deploy system",
                    "example": "/deploy production #version 2.1"
                },
                {
                    "name": "test",
                    "description": "Run tests",
                    "example": "/test automated #QA suite"
                },
                {
                    "name": "approve",
                    "description": "Approve request",
                    "example": "/approve executive #final plan"
                }
            ],
            "bot_roles": [
                "CEO", "CTO", "CFO", "VP Engineering", "VP Product",
                "VP Sales", "VP Marketing", "Content Manager",
                "Account Executive", "Software Engineer", "QA Engineer"
            ],
            "domains": [
                "executive", "technology", "finance", "engineering",
                "product", "sales", "marketing"
            ],
            "workflows": self.get_available_workflows()
        }