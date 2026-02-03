"""
Murphy System - Librarian Intent Mapping System

The Librarian is Murphy's intelligent guide that understands user intent
and maps it to system capabilities.
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import json
import re


class IntentCategory(Enum):
    """Categories of user intent"""
    QUERY = "query"              # User wants information
    ACTION = "action"            # User wants to execute something
    GUIDANCE = "guidance"        # User needs help deciding
    LEARNING = "learning"        # User wants to understand
    CREATION = "creation"        # User wants to create something
    ANALYSIS = "analysis"        # User wants analysis/insights
    TROUBLESHOOTING = "troubleshooting"  # User has a problem
    EXPLORATION = "exploration"  # User wants to explore options


class ConfidenceLevel(Enum):
    """Confidence in intent classification"""
    VERY_HIGH = "very_high"  # 90-100%
    HIGH = "high"            # 75-89%
    MEDIUM = "medium"        # 60-74%
    LOW = "low"              # 40-59%
    VERY_LOW = "very_low"    # <40%


@dataclass
class Intent:
    """Represents a classified user intent"""
    category: IntentCategory
    confidence: float
    keywords: List[str]
    entities: Dict[str, str]
    suggested_commands: List[str]
    suggested_workflow: Optional[Dict] = None
    context: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class LibrarianResponse:
    """Response from the Librarian"""
    intent: Intent
    message: str
    commands: List[str]
    workflow: Optional[Dict] = None
    follow_up_questions: List[str] = field(default_factory=list)
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM


class IntentClassifier:
    """Classifies user input into intent categories"""
    
    # Intent patterns for rule-based classification
    INTENT_PATTERNS = {
        IntentCategory.QUERY: [
            r'\b(what|who|where|when|why|how|show|list|get|find|search)\b',
            r'\b(status|info|information|details|about)\b',
        ],
        IntentCategory.ACTION: [
            r'\b(create|make|build|generate|start|run|execute|do)\b',
            r'\b(initialize|setup|configure|deploy|launch)\b',
        ],
        IntentCategory.GUIDANCE: [
            r'\b(help|guide|assist|recommend|suggest|advise)\b',
            r'\b(should|could|would|best way|how to)\b',
        ],
        IntentCategory.LEARNING: [
            r'\b(learn|understand|explain|teach|tutorial)\b',
            r'\b(what is|how does|why does)\b',
        ],
        IntentCategory.CREATION: [
            r'\b(design|develop|write|compose|draft)\b',
            r'\b(document|report|proposal|plan|specification)\b',
        ],
        IntentCategory.ANALYSIS: [
            r'\b(analyze|evaluate|assess|review|examine)\b',
            r'\b(compare|contrast|measure|calculate)\b',
        ],
        IntentCategory.TROUBLESHOOTING: [
            r'\b(fix|solve|debug|error|problem|issue|broken)\b',
            r'\b(not working|failed|wrong)\b',
        ],
        IntentCategory.EXPLORATION: [
            r'\b(explore|discover|investigate|browse)\b',
            r'\b(options|possibilities|alternatives)\b',
        ],
    }
    
    # Entity extraction patterns
    ENTITY_PATTERNS = {
        'domain': r'\b(business|engineering|financial|legal|operations|marketing|hr|sales|product)\b',
        'artifact_type': r'\b(document|report|proposal|plan|specification|design|code)\b',
        'action_type': r'\b(create|analyze|review|generate|execute)\b',
        'system_component': r'\b(agent|state|gate|swarm|constraint|domain)\b',
    }
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.classification_history = []
    
    async def classify_intent(self, user_input: str, context: Dict = None) -> Intent:
        """
        Classify user intent using hybrid approach:
        1. Rule-based pattern matching
        2. LLM-based classification (if available)
        3. Context-aware refinement
        """
        context = context or {}
        
        # Step 1: Rule-based classification
        rule_based_intent = self._rule_based_classification(user_input)
        
        # Step 2: LLM-based classification (if available)
        if self.llm_client:
            llm_intent = await self._llm_based_classification(user_input, context)
            # Combine rule-based and LLM results
            final_intent = self._combine_classifications(rule_based_intent, llm_intent)
        else:
            final_intent = rule_based_intent
        
        # Step 3: Extract entities
        entities = self._extract_entities(user_input)
        final_intent.entities = entities
        
        # Step 4: Add context
        final_intent.context = context
        
        # Store in history
        self.classification_history.append(final_intent)
        
        return final_intent
    
    def _rule_based_classification(self, user_input: str) -> Intent:
        """Classify intent using pattern matching"""
        user_input_lower = user_input.lower()
        
        # Score each intent category
        scores = {}
        matched_keywords = {}
        
        for category, patterns in self.INTENT_PATTERNS.items():
            score = 0
            keywords = []
            for pattern in patterns:
                matches = re.findall(pattern, user_input_lower)
                if matches:
                    score += len(matches)
                    keywords.extend(matches)
            scores[category] = score
            matched_keywords[category] = keywords
        
        # Get highest scoring category
        if max(scores.values()) == 0:
            # No patterns matched, default to QUERY
            category = IntentCategory.QUERY
            confidence = 0.3
            keywords = []
        else:
            category = max(scores, key=scores.get)
            total_matches = sum(scores.values())
            confidence = min(scores[category] / total_matches, 1.0) if total_matches > 0 else 0.5
            keywords = matched_keywords[category]
        
        return Intent(
            category=category,
            confidence=confidence,
            keywords=keywords,
            entities={},
            suggested_commands=[]
        )
    
    async def _llm_based_classification(self, user_input: str, context: Dict) -> Intent:
        """Classify intent using LLM"""
        prompt = f"""Classify the user's intent from the following input:

User Input: "{user_input}"

Context: {json.dumps(context, indent=2)}

Classify into one of these categories:
- QUERY: User wants information
- ACTION: User wants to execute something
- GUIDANCE: User needs help deciding
- LEARNING: User wants to understand
- CREATION: User wants to create something
- ANALYSIS: User wants analysis/insights
- TROUBLESHOOTING: User has a problem
- EXPLORATION: User wants to explore options

Respond in JSON format:
{{
    "category": "CATEGORY_NAME",
    "confidence": 0.85,
    "keywords": ["keyword1", "keyword2"],
    "reasoning": "Brief explanation"
}}"""

        try:
            response = await self.llm_client.generate(prompt, temperature=0.3)
            result = json.loads(response)
            
            return Intent(
                category=IntentCategory[result['category']],
                confidence=result['confidence'],
                keywords=result['keywords'],
                entities={},
                suggested_commands=[]
            )
        except Exception as e:
            # Fallback to rule-based if LLM fails
            return self._rule_based_classification(user_input)
    
    def _combine_classifications(self, rule_based: Intent, llm_based: Intent) -> Intent:
        """Combine rule-based and LLM classifications"""
        # Weight: 40% rule-based, 60% LLM
        if rule_based.category == llm_based.category:
            # Agreement - high confidence
            combined_confidence = (rule_based.confidence * 0.4 + llm_based.confidence * 0.6) * 1.2
            combined_confidence = min(combined_confidence, 1.0)
            category = rule_based.category
        else:
            # Disagreement - use LLM but lower confidence
            combined_confidence = llm_based.confidence * 0.7
            category = llm_based.category
        
        # Combine keywords
        combined_keywords = list(set(rule_based.keywords + llm_based.keywords))
        
        return Intent(
            category=category,
            confidence=combined_confidence,
            keywords=combined_keywords,
            entities={},
            suggested_commands=[]
        )
    
    def _extract_entities(self, user_input: str) -> Dict[str, str]:
        """Extract entities from user input"""
        entities = {}
        user_input_lower = user_input.lower()
        
        for entity_type, pattern in self.ENTITY_PATTERNS.items():
            matches = re.findall(pattern, user_input_lower)
            if matches:
                entities[entity_type] = matches[0]  # Take first match
        
        return entities


class CapabilityMapper:
    """Maps intents to system capabilities"""
    
    # Command mappings for each intent category
    INTENT_TO_COMMANDS = {
        IntentCategory.QUERY: {
            'general': ['/status', '/help'],
            'agents': ['/org agents', '/org chart'],
            'states': ['/state list'],
            'gates': ['/gate list'],
            'domains': ['/domain list'],
            'swarms': ['/swarm status'],
        },
        IntentCategory.ACTION: {
            'initialize': ['/initialize'],
            'create_state': ['/state evolve <id>'],
            'create_agent': ['/org assign <role> <agent>'],
            'run_swarm': ['/swarm execute <type>'],
            'validate': ['/gate validate <id>'],
        },
        IntentCategory.GUIDANCE: {
            'general': ['/librarian guide'],
            'commands': ['/help <command>'],
            'workflow': ['/librarian workflow'],
        },
        IntentCategory.LEARNING: {
            'system': ['/help', '/librarian overview'],
            'component': ['/help <component>'],
            'transcripts': ['/librarian transcripts'],
        },
        IntentCategory.CREATION: {
            'document': ['/document create <type>'],
            'domain': ['/domain create <name>'],
            'constraint': ['/constraint add <type>'],
        },
        IntentCategory.ANALYSIS: {
            'domain': ['/domain analyze'],
            'impact': ['/domain impact'],
            'constraints': ['/constraint validate'],
        },
        IntentCategory.TROUBLESHOOTING: {
            'general': ['/status', '/llm status'],
            'verification': ['/verify state <id>'],
        },
        IntentCategory.EXPLORATION: {
            'general': ['/librarian search <query>'],
            'knowledge': ['/librarian knowledge'],
        },
    }
    
    def __init__(self):
        self.mapping_history = []
    
    def map_to_commands(self, intent: Intent) -> List[str]:
        """Convert intent to executable commands"""
        commands = []
        
        # Get commands for intent category
        category_commands = self.INTENT_TO_COMMANDS.get(intent.category, {})
        
        # Match based on entities
        if intent.entities:
            for entity_type, entity_value in intent.entities.items():
                if entity_value in category_commands:
                    commands.extend(category_commands[entity_value])
        
        # Add general commands if no specific match
        if not commands and 'general' in category_commands:
            commands.extend(category_commands['general'])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_commands = []
        for cmd in commands:
            if cmd not in seen:
                seen.add(cmd)
                unique_commands.append(cmd)
        
        return unique_commands
    
    def suggest_workflow(self, intent: Intent) -> Optional[Dict]:
        """Suggest multi-step workflow for complex intents"""
        workflows = {
            IntentCategory.CREATION: {
                'name': 'Document Creation Workflow',
                'steps': [
                    {'command': '/document create <type>', 'description': 'Create initial document'},
                    {'command': '/document magnify <domain>', 'description': 'Add domain expertise'},
                    {'command': '/document solidify', 'description': 'Prepare for generation'},
                    {'command': '/swarm execute CREATIVE', 'description': 'Generate content'},
                ],
            },
            IntentCategory.ANALYSIS: {
                'name': 'Analysis Workflow',
                'steps': [
                    {'command': '/domain analyze', 'description': 'Analyze domain coverage'},
                    {'command': '/constraint validate', 'description': 'Check constraints'},
                    {'command': '/domain impact', 'description': 'Assess cross-domain impact'},
                    {'command': '/swarm execute ANALYTICAL', 'description': 'Generate analysis'},
                ],
            },
            IntentCategory.ACTION: {
                'name': 'System Initialization Workflow',
                'steps': [
                    {'command': '/initialize', 'description': 'Initialize system'},
                    {'command': '/domain list', 'description': 'Review available domains'},
                    {'command': '/constraint add <type>', 'description': 'Add constraints'},
                    {'command': '/gate list', 'description': 'Review safety gates'},
                ],
            },
        }
        
        return workflows.get(intent.category)


class LibrarianSystem:
    """Main Librarian system that provides intelligent guidance"""
    
    def __init__(self, llm_client=None, groq_client=None, aristotle_client=None):
        self.classifier = IntentClassifier(llm_client or groq_client)
        self.mapper = CapabilityMapper()
        self.llm_client = llm_client or groq_client
        self.groq_client = groq_client
        self.aristotle_client = aristotle_client
        self.conversation_history = []
        self.knowledge_base = self._build_knowledge_base()
    
    def _build_knowledge_base(self) -> Dict:
        """Build knowledge base of system capabilities"""
        return {
            'commands': {
                'help': 'Show available commands and help',
                'status': 'Show system status',
                'initialize': 'Initialize the Murphy System',
                'state': 'Manage system states',
                'org': 'Manage organizational structure',
                'swarm': 'Execute swarm operations',
                'gate': 'Manage validation gates',
                'domain': 'Manage business domains',
                'constraint': 'Manage system constraints',
                'document': 'Manage living documents',
                'llm': 'Manage LLM integrations',
            },
            'concepts': {
                'state': 'A snapshot of system condition with parent-child relationships',
                'agent': 'Autonomous entity executing tasks within domains',
                'gate': 'Validation checkpoint for quality and compliance',
                'swarm': 'Parallel execution of tasks by multiple agents',
                'domain': 'Business area with specific expertise',
                'constraint': 'Limitation or requirement that must be satisfied',
                'living_document': 'Document that evolves from fuzzy to precise',
            },
            'workflows': {
                'initialization': 'Initialize → Add Domains → Add Constraints → Create Gates',
                'document_creation': 'Create → Magnify → Simplify → Solidify → Generate',
                'analysis': 'Analyze Domains → Validate Constraints → Assess Impact → Generate Report',
            },
        }
    
    async def ask(self, user_input: str, context: Dict = None) -> LibrarianResponse:
        """
        Main entry point for Librarian interaction
        
        Args:
            user_input: User's question or request
            context: Optional context (recent commands, current state, etc.)
        
        Returns:
            LibrarianResponse with guidance and suggestions
        """
        context = context or {}
        
        # Classify intent
        intent = await self.classifier.classify_intent(user_input, context)
        
        # Map to commands
        commands = self.mapper.map_to_commands(intent)
        intent.suggested_commands = commands
        
        # Get workflow suggestion
        workflow = self.mapper.suggest_workflow(intent)
        intent.suggested_workflow = workflow
        
        # Generate response message
        message = await self._generate_response_message(intent, user_input)
        
        # Generate follow-up questions
        follow_up = self._generate_follow_up_questions(intent)
        
        # Determine confidence level
        confidence_level = self._get_confidence_level(intent.confidence)
        
        # Store in conversation history
        response = LibrarianResponse(
            intent=intent,
            message=message,
            commands=commands,
            workflow=workflow,
            follow_up_questions=follow_up,
            confidence_level=confidence_level
        )
        self.conversation_history.append({
            'user_input': user_input,
            'response': response,
            'timestamp': datetime.now()
        })
        
        return response
    
    async def _generate_response_message(self, intent: Intent, user_input: str) -> str:
        """Generate helpful response message"""
        if self.llm_client:
            # Use LLM to generate personalized response
            prompt = f"""Generate a helpful response for the user based on their intent.

User Input: "{user_input}"
Intent Category: {intent.category.value}
Confidence: {intent.confidence:.2f}
Suggested Commands: {', '.join(intent.suggested_commands)}

Generate a friendly, helpful response that:
1. Acknowledges their intent
2. Suggests the most relevant commands
3. Provides brief guidance on next steps

Keep it concise (2-3 sentences)."""

            try:
                return await self.llm_client.generate(prompt, temperature=0.7)
            except:
                pass
        
        # Fallback to template-based response
        templates = {
            IntentCategory.QUERY: f"I can help you find that information. Try these commands: {', '.join(intent.suggested_commands[:3])}",
            IntentCategory.ACTION: f"Let's get that done! Start with: {intent.suggested_commands[0] if intent.suggested_commands else '/help'}",
            IntentCategory.GUIDANCE: f"I'm here to guide you. Based on your request, I recommend: {', '.join(intent.suggested_commands[:2])}",
            IntentCategory.LEARNING: f"Great question! To learn more, try: {', '.join(intent.suggested_commands[:2])}",
            IntentCategory.CREATION: f"Let's create that together. Here's the workflow: {intent.suggested_workflow['name'] if intent.suggested_workflow else 'Start with /document create'}",
            IntentCategory.ANALYSIS: f"I'll help you analyze that. Begin with: {intent.suggested_commands[0] if intent.suggested_commands else '/domain analyze'}",
            IntentCategory.TROUBLESHOOTING: f"Let's troubleshoot this. First, check: {intent.suggested_commands[0] if intent.suggested_commands else '/status'}",
            IntentCategory.EXPLORATION: f"Let's explore! Try: {', '.join(intent.suggested_commands[:2])}",
        }
        
        return templates.get(intent.category, "I'm here to help! Try /help to see available commands.")
    
    def _generate_follow_up_questions(self, intent: Intent) -> List[str]:
        """Generate relevant follow-up questions"""
        follow_ups = {
            IntentCategory.QUERY: [
                "Would you like more details about any specific component?",
                "Should I show you related commands?",
            ],
            IntentCategory.ACTION: [
                "Would you like me to guide you through the steps?",
                "Do you need to set up any constraints first?",
            ],
            IntentCategory.GUIDANCE: [
                "Would you like to see a complete workflow?",
                "Should I explain any of these concepts?",
            ],
            IntentCategory.LEARNING: [
                "Would you like to see examples?",
                "Should I explain related concepts?",
            ],
            IntentCategory.CREATION: [
                "What type of document would you like to create?",
                "Which domains should I include?",
            ],
            IntentCategory.ANALYSIS: [
                "Which domains should I analyze?",
                "Would you like a detailed report?",
            ],
        }
        
        return follow_ups.get(intent.category, [])
    
    def _get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Convert confidence score to level"""
        if confidence >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif confidence >= 0.75:
            return ConfidenceLevel.HIGH
        elif confidence >= 0.6:
            return ConfidenceLevel.MEDIUM
        elif confidence >= 0.4:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    def search_knowledge(self, query: str) -> List[Dict]:
        """Search knowledge base"""
        results = []
        query_lower = query.lower()
        
        # Search commands
        for cmd, desc in self.knowledge_base['commands'].items():
            if query_lower in cmd.lower() or query_lower in desc.lower():
                results.append({
                    'type': 'command',
                    'name': cmd,
                    'description': desc,
                    'relevance': 0.9
                })
        
        # Search concepts
        for concept, desc in self.knowledge_base['concepts'].items():
            if query_lower in concept.lower() or query_lower in desc.lower():
                results.append({
                    'type': 'concept',
                    'name': concept,
                    'description': desc,
                    'relevance': 0.8
                })
        
        # Search workflows
        for workflow, desc in self.knowledge_base['workflows'].items():
            if query_lower in workflow.lower() or query_lower in desc.lower():
                results.append({
                    'type': 'workflow',
                    'name': workflow,
                    'description': desc,
                    'relevance': 0.7
                })
        
        # Sort by relevance
        results.sort(key=lambda x: x['relevance'], reverse=True)
        
        return results
    
    def get_transcripts(self, limit: int = 10) -> List[Dict]:
        """Get recent conversation transcripts"""
        return self.conversation_history[-limit:]
    
    def get_overview(self) -> Dict:
        """Get system overview"""
        return {
            'total_interactions': len(self.conversation_history),
            'intent_distribution': self._get_intent_distribution(),
            'most_common_commands': self._get_common_commands(),
            'knowledge_base_size': {
                'commands': len(self.knowledge_base['commands']),
                'concepts': len(self.knowledge_base['concepts']),
                'workflows': len(self.knowledge_base['workflows']),
            }
        }
    
    def _get_intent_distribution(self) -> Dict[str, int]:
        """Get distribution of intent categories"""
        distribution = {}
        for entry in self.conversation_history:
            category = entry['response'].intent.category.value
            distribution[category] = distribution.get(category, 0) + 1
        return distribution
    
    def _get_common_commands(self) -> List[Tuple[str, int]]:
        """Get most commonly suggested commands"""
        command_counts = {}
        for entry in self.conversation_history:
            for cmd in entry['response'].commands:
                command_counts[cmd] = command_counts.get(cmd, 0) + 1
        
        # Sort by count
        sorted_commands = sorted(command_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_commands[:10]


# Example usage and testing
if __name__ == "__main__":
    async def test_librarian():
        """Test the Librarian system"""
        librarian = LibrarianSystem()
        
        test_queries = [
            "How do I create a new document?",
            "Show me the system status",
            "I need help deciding which domain to use",
            "What is a state?",
            "Analyze the business domain",
            "Something is broken with my agent",
            "I want to explore different options",
        ]
        
        print("=== Librarian System Test ===\n")
        
        for query in test_queries:
            print(f"User: {query}")
            response = await librarian.ask(query)
            print(f"Intent: {response.intent.category.value} (confidence: {response.intent.confidence:.2f})")
            print(f"Librarian: {response.message}")
            print(f"Suggested Commands: {', '.join(response.commands)}")
            if response.workflow:
                print(f"Workflow: {response.workflow['name']}")
            print()
    
    # Run test
    asyncio.run(test_librarian())