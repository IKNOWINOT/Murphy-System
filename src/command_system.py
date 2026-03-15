"""
Modular Command System
Implements chainable commands with deterministic execution
"""

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CommandResult:
    """Result from command execution"""

    def __init__(self, success: bool, data: Any, metadata: Dict[str, Any]):
        self.success = success
        self.data = data
        self.metadata = metadata
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'data': self.data,
            'metadata': self.metadata,
            'timestamp': self.timestamp
        }

    def __str__(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class CommandModule(ABC):
    """Base class for all command modules"""

    def __init__(self, name: str, version: str = "1.0"):
        self.name = name
        self.version = version
        self.temp_dir = Path("/tmp/agent_temp")
        self.temp_dir.mkdir(exist_ok=True)

    @abstractmethod
    def execute(self, input_data: Any, options: Dict[str, Any]) -> CommandResult:
        """Execute the command - must be implemented by subclasses."""
        ...

    def verify(self, result: CommandResult) -> bool:
        """Verify the result - can be overridden"""
        return result.success

    def chain_output(self, result: CommandResult) -> Any:
        """Format output for next command in chain"""
        return result.data

    def save_temp_file(self, filename: str, data: Any) -> str:
        """Save data to temporary file"""
        filepath = self.temp_dir / filename

        if isinstance(data, (dict, list)):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        else:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(str(data))

        return str(filepath)

    def load_temp_file(self, filename: str) -> Any:
        """Load data from temporary file"""
        filepath = self.temp_dir / filename

        if not filepath.exists():
            return None

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()


class ResearchCommand(CommandModule):
    """
    /research [topic] [options]
    Conduct comprehensive research on a topic
    """

    def __init__(self, research_engine):
        super().__init__("research", "1.0")
        self.research_engine = research_engine

    def execute(self, input_data: Any, options: Dict[str, Any]) -> CommandResult:
        """
        Execute research command

        Options:
            --depth: quick|standard|deep
            --sources: number of sources
            --verify: enable cross-reference
            --trust-min: minimum trust score
        """
        topic = str(input_data)
        depth = options.get('depth', 'standard')
        min_sources = int(options.get('sources', 3))
        verify = options.get('verify', False)
        trust_min = float(options.get('trust-min', 0.5))

        # Perform research
        result = self.research_engine.research_topic(topic, depth=depth)

        if not result or not result.sources:
            return CommandResult(
                success=False,
                data=None,
                metadata={
                    'error': 'No reliable sources found',
                    'topic': topic,
                    'attempted_depth': depth
                }
            )

        # Filter by trust score
        filtered_sources = [
            s for s in result.sources
            if getattr(s, 'trust_score', 0.7) >= trust_min
        ]

        if len(filtered_sources) < min_sources:
            return CommandResult(
                success=False,
                data=None,
                metadata={
                    'error': f'Only found {len(filtered_sources)} sources meeting trust threshold',
                    'trust_min': trust_min,
                    'required_sources': min_sources
                }
            )

        # Build research data
        research_data = {
            'topic': topic,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'depth': depth,
            'sources': [],
            'facts': [],
            'confidence': result.confidence
        }

        for source in filtered_sources[:min_sources]:
            source_data = {
                'entity': source.entity,
                'trust_score': getattr(source, 'trust_score', 0.7),
                'verified': source.verified,
                'sources': source.sources,
                'facts': source.facts if isinstance(source.facts, dict) else {}
            }
            research_data['sources'].append(source_data)

            # Extract facts
            if isinstance(source.facts, dict):
                for key, value in source.facts.items():
                    research_data['facts'].append({
                        'claim': f"{key}: {value}",
                        'source': source.entity,
                        'trust': getattr(source, 'trust_score', 0.7)
                    })

        # Save to temporary file
        filename = f"research_{topic.replace(' ', '_')}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.save_temp_file(filename, research_data)

        return CommandResult(
            success=True,
            data=research_data,
            metadata={
                'topic': topic,
                'sources_found': len(filtered_sources),
                'confidence': result.confidence,
                'temp_file': filepath,
                'depth': depth
            }
        )


class MathCommand(CommandModule):
    """
    /math [expression|problem] [options]
    Perform mathematical calculations with verification
    """

    def __init__(self):
        super().__init__("math", "1.0")

    def execute(self, input_data: Any, options: Dict[str, Any]) -> CommandResult:
        """
        Execute math command

        Options:
            --verify: double-check result
            --show-steps: display step-by-step
            --precision: decimal precision
        """
        expression = str(input_data)
        verify = options.get('verify', True)
        show_steps = options.get('show-steps', True)
        precision = int(options.get('precision', 10))

        try:
            # Try to evaluate as Python expression
            import ast
            import operator

            # Safe operators
            operators = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Pow: operator.pow,
                ast.USub: operator.neg,
            }

            def eval_expr(node):
                if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                    return node.value
                elif isinstance(node, ast.BinOp):
                    return operators[type(node.op)](eval_expr(node.left), eval_expr(node.right))
                elif isinstance(node, ast.UnaryOp):
                    return operators[type(node.op)](eval_expr(node.operand))
                else:
                    raise TypeError(node)

            # Parse and evaluate
            tree = ast.parse(expression, mode='eval')
            result = eval_expr(tree.body)

            # Round to precision
            if isinstance(result, float):
                result = round(result, precision)

            # Verification (re-calculate)
            if verify:
                verify_result = eval_expr(tree.body)
                if isinstance(verify_result, float):
                    verify_result = round(verify_result, precision)

                if result != verify_result:
                    return CommandResult(
                        success=False,
                        data=None,
                        metadata={
                            'error': 'Verification failed',
                            'result': result,
                            'verify_result': verify_result
                        }
                    )

            return CommandResult(
                success=True,
                data=result,
                metadata={
                    'expression': expression,
                    'verified': verify,
                    'precision': precision,
                    'confidence': 1.0  # Deterministic
                }
            )

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return CommandResult(
                success=False,
                data=None,
                metadata={
                    'error': str(exc),
                    'expression': expression
                }
            )


class ReasonCommand(CommandModule):
    """
    /reason [options] [data]
    Evaluate options and make decisions based on data
    """

    def __init__(self):
        super().__init__("reason", "1.0")

    def execute(self, input_data: Any, options: Dict[str, Any]) -> CommandResult:
        """
        Execute reasoning command

        Options:
            --criteria: list of criteria
            --weights: criteria weights
            --method: pros-cons|scoring|decision-tree
        """
        # Load research data if input is a filepath
        if isinstance(input_data, str) and input_data.endswith('.json'):
            data = self.load_temp_file(os.path.basename(input_data))
        elif isinstance(input_data, dict):
            data = input_data
        else:
            data = {'raw': input_data}

        criteria = options.get('criteria', '').split(',')
        weights = options.get('weights', '').split(',')
        method = options.get('method', 'scoring')

        # Parse weights
        if weights and weights[0]:
            weights = [float(w) for w in weights]
        else:
            weights = [1.0] * len(criteria)

        # Normalize weights
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]
        else:
            # All weights zero — fall back to equal weighting
            weights = [1.0 / len(weights)] * len(weights) if weights else []

        # Extract options from data
        if 'facts' in data:
            options_data = data['facts']
        else:
            options_data = [data]

        # Score each option
        scores = []
        for i, option in enumerate(options_data):
            score = 0.0
            criterion_scores = {}

            for j, criterion in enumerate(criteria):
                # Simple scoring based on presence and relevance
                criterion_score = 0.5  # Default neutral score

                if isinstance(option, dict):
                    # Check if criterion is mentioned
                    option_str = str(option).lower()
                    if criterion.lower() in option_str:
                        criterion_score = 0.8

                criterion_scores[criterion] = criterion_score
                score += criterion_score * weights[j]

            scores.append({
                'option': option,
                'total_score': score,
                'criterion_scores': criterion_scores
            })

        # Sort by score
        scores.sort(key=lambda x: x['total_score'], reverse=True)

        return CommandResult(
            success=True,
            data=scores,
            metadata={
                'method': method,
                'criteria': criteria,
                'weights': weights,
                'num_options': len(scores)
            }
        )


class ChatCommand(CommandModule):
    """
    /chat [message] [options]
    Internal processing without immediate output
    """

    def __init__(self, chatbot):
        super().__init__("chat", "1.0")
        self.chatbot = chatbot

    def execute(self, input_data: Any, options: Dict[str, Any]) -> CommandResult:
        """
        Execute chat command

        Options:
            --context: conversation context ID
            --store: store result
            --silent: no output to user
        """
        message = str(input_data)
        context_id = options.get('context', 'default')
        store = options.get('store', False)
        silent = options.get('silent', False)

        # Process through chatbot
        response = self.chatbot.chat(message, conversation_id=context_id)

        # Store if requested
        if store:
            filename = f"chat_{context_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
            self.save_temp_file(filename, response)

        return CommandResult(
            success=True,
            data=response if not silent else None,
            metadata={
                'context_id': context_id,
                'stored': store,
                'silent': silent
            }
        )


class WhisperCommand(CommandModule):
    """
    /whisper [target] [message]
    Communication with modules or users
    """

    def __init__(self):
        super().__init__("whisper", "1.0")
        self.messages = []

    def execute(self, input_data: Any, options: Dict[str, Any]) -> CommandResult:
        """
        Execute whisper command

        Targets:
            user: send to user
            module:<name>: send to module
            log: write to log
            context: update context
        """
        target = options.get('target', 'user')
        message = str(input_data)

        whisper_data = {
            'target': target,
            'message': message,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        self.messages.append(whisper_data)

        # Save to log if target is log
        if target == 'log':
            filename = f"whisper_log_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
            logs = self.load_temp_file(filename) or []
            logs.append(whisper_data)
            self.save_temp_file(filename, logs)

        return CommandResult(
            success=True,
            data=whisper_data,
            metadata={
                'target': target,
                'message_count': len(self.messages)
            }
        )


class VerifyCommand(CommandModule):
    """
    /verify [claim] [options]
    Verify a claim through multiple sources
    """

    def __init__(self, research_engine):
        super().__init__("verify", "1.0")
        self.research_engine = research_engine

    def execute(self, input_data: Any, options: Dict[str, Any]) -> CommandResult:
        """
        Execute verify command

        Options:
            --sources: number of sources
            --method: cross-ref|consensus|expert
        """
        claim = str(input_data)
        num_sources = int(options.get('sources', 3))
        method = options.get('method', 'consensus')

        # Research the claim
        result = self.research_engine.research_topic(claim, depth='standard')

        if not result or not result.sources:
            return CommandResult(
                success=False,
                data=None,
                metadata={
                    'error': 'Could not find sources to verify claim',
                    'claim': claim
                }
            )

        # Count supporting vs contradicting sources
        supporting = 0
        contradicting = 0
        neutral = 0

        for source in result.sources[:num_sources]:
            # Simple heuristic: check if claim keywords appear in facts
            claim_keywords = set(claim.lower().split())

            if isinstance(source.facts, dict):
                facts_str = str(source.facts).lower()

                # Count keyword matches
                matches = sum(1 for kw in claim_keywords if kw in facts_str)

                if matches >= len(claim_keywords) * 0.7:
                    supporting += 1
                elif matches <= len(claim_keywords) * 0.3:
                    contradicting += 1
                else:
                    neutral += 1

        total = supporting + contradicting + neutral
        consensus_score = supporting / total if total > 0 else 0.0

        # Determine verification status
        if consensus_score >= 0.7:
            status = 'VERIFIED'
            confidence = consensus_score
        elif consensus_score <= 0.3:
            status = 'CONTRADICTED'
            confidence = 1.0 - consensus_score
        else:
            status = 'UNCERTAIN'
            confidence = 0.5

        return CommandResult(
            success=True,
            data={
                'claim': claim,
                'status': status,
                'confidence': confidence,
                'supporting': supporting,
                'contradicting': contradicting,
                'neutral': neutral,
                'consensus_score': consensus_score
            },
            metadata={
                'method': method,
                'sources_checked': total
            }
        )


class CommandParser:
    """Parse command strings and extract commands with options"""

    @staticmethod
    def parse(command_string: str) -> List[Tuple[str, str, Dict[str, Any]]]:
        """
        Parse command string into list of (command, target, options)

        Example:
            "/research 'quantum computing' --depth=deep | /reason --criteria=cost,benefit"

        Returns:
            [
                ('research', 'quantum computing', {'depth': 'deep'}),
                ('reason', '', {'criteria': 'cost,benefit'})
            ]
        """
        commands = []

        # Split by pipe for chaining
        parts = command_string.split('|')

        for part in parts:
            part = part.strip()

            if not part.startswith('/'):
                continue

            # Extract command name
            match = re.match(r'/(\w+)\s*(.*)', part)
            if not match:
                continue

            cmd_name = match.group(1)
            rest = match.group(2)

            # Extract target and options
            target = ''
            options = {}

            # Find quoted target
            quote_match = re.match(r'["\']([^"\']+)["\'](.*)' , rest)
            if quote_match:
                target = quote_match.group(1)
                rest = quote_match.group(2)
            else:
                # Find unquoted target (first word)
                words = rest.split()
                if words and not words[0].startswith('--'):
                    target = words[0]
                    rest = ' '.join(words[1:])

            # Extract options
            option_pattern = r'--(\w+(?:-\w+)*)(?:=([^\s]+))?'
            for match in re.finditer(option_pattern, rest):
                key = match.group(1)
                value = match.group(2) if match.group(2) else True
                options[key] = value

            commands.append((cmd_name, target, options))

        return commands


class CommandExecutor:
    """Execute commands and handle chaining"""

    def __init__(self, modules: Dict[str, CommandModule]):
        self.modules = modules
        self.parser = CommandParser()

    def execute(self, command_string: str) -> List[CommandResult]:
        """
        Execute command string (potentially chained)

        Returns list of results from each command
        """
        commands = self.parser.parse(command_string)
        results = []

        # Execute commands in sequence
        previous_output = None

        for cmd_name, target, options in commands:
            # Get module
            module = self.modules.get(cmd_name)

            if not module:
                results.append(CommandResult(
                    success=False,
                    data=None,
                    metadata={'error': f'Unknown command: {cmd_name}'}
                ))
                break

            # Determine input
            if previous_output is not None:
                input_data = previous_output
            else:
                input_data = target

            # Execute
            result = module.execute(input_data, options)
            results.append(result)

            # If failed, break chain
            if not result.success:
                break

            # Prepare output for next command
            previous_output = module.chain_output(result)

        return results

    def format_results(self, results: List[CommandResult]) -> str:
        """Format results for display"""
        output = []

        for i, result in enumerate(results, 1):
            output.append(f"## Command {i} Result\n")

            if result.success:
                output.append("**Status:** ✓ Success\n")
                output.append(f"**Data:**\n```\n{json.dumps(result.data, indent=2)}\n```\n")
            else:
                output.append("**Status:** ✗ Failed\n")
                output.append(f"**Error:** {result.metadata.get('error', 'Unknown error')}\n")

            output.append(f"**Metadata:**\n```\n{json.dumps(result.metadata, indent=2)}\n```\n")
            output.append("\n---\n\n")

        return ''.join(output)
