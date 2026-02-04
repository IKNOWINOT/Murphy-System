# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Agent Communication System - Email Chatter Between Agents
Handles inter-agent messaging, decision gates, and token cost analysis
"""

import json
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class MessageType(Enum):
    """Types of inter-agent messages"""
    TASK_ASSIGNMENT = "task_assignment"
    QUESTION = "question"
    ANSWER = "answer"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"
    STATUS_UPDATE = "status_update"
    COST_ANALYSIS = "cost_analysis"
    REVENUE_PROJECTION = "revenue_projection"
    CLARIFICATION = "clarification"

class ConfidenceLevel(Enum):
    """Confidence levels for agent decisions"""
    GREEN = "green"  # 95%+ - Ready to execute
    YELLOW = "yellow"  # 70-94% - Needs clarification
    RED = "red"  # <70% - Major information needed

@dataclass
class DecisionGate:
    """A decision point that an agent must consider"""
    gate_id: str
    question: str
    options: List[str]
    selected_option: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""
    token_cost: int = 0
    revenue_impact: float = 0.0

@dataclass
class AgentMessage:
    """A message between agents (email chatter)"""
    message_id: str
    from_agent: str
    to_agent: str
    message_type: MessageType
    subject: str
    body: str
    timestamp: str
    thread_id: Optional[str] = None
    requires_response: bool = False
    attachments: List[Dict] = None
    
    def to_dict(self):
        data = asdict(self)
        data['message_type'] = self.message_type.value
        return data

@dataclass
class AgentTaskReview:
    """Complete review state for an agent task"""
    task_id: str
    agent_name: str
    agent_role: str
    
    # LLM Generative Side
    llm_state: Dict  # What the LLM generated
    llm_prompt: str
    llm_response: str
    llm_tokens_used: int
    
    # Librarian Interpretation Side
    librarian_interpretation: str  # How to best execute
    librarian_command_chain: List[str]
    librarian_confidence: float
    
    # Decision Gates
    gates: List[DecisionGate]
    overall_confidence: ConfidenceLevel
    
    # Cost Analysis
    token_cost: int
    revenue_potential: float
    cost_benefit_ratio: float
    
    # Clarifying Questions
    questions: List[Dict]  # Questions to boost confidence
    
    # Communication Thread
    message_thread: List[AgentMessage]
    
    def to_dict(self):
        data = asdict(self)
        data['overall_confidence'] = self.overall_confidence.value
        data['message_thread'] = [msg.to_dict() for msg in self.message_thread]
        return data

class AgentCommunicationHub:
    """Central hub for all inter-agent communication"""
    
    def __init__(self, librarian, llm_system):
        self.librarian = librarian
        self.llm_system = llm_system
        self.message_threads = {}  # thread_id -> List[AgentMessage]
        self.agent_inboxes = {}  # agent_name -> List[AgentMessage]
        self.task_reviews = {}  # task_id -> AgentTaskReview
        
    def send_message(self, from_agent: str, to_agent: str, 
                    message_type: MessageType, subject: str, body: str,
                    thread_id: Optional[str] = None,
                    requires_response: bool = False,
                    attachments: List[Dict] = None) -> AgentMessage:
        """Send a message from one agent to another"""
        
        message_id = f"msg_{datetime.now().timestamp()}"
        if not thread_id:
            thread_id = f"thread_{message_id}"
        
        message = AgentMessage(
            message_id=message_id,
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            subject=subject,
            body=body,
            timestamp=datetime.now().isoformat(),
            thread_id=thread_id,
            requires_response=requires_response,
            attachments=attachments or []
        )
        
        # Add to thread
        if thread_id not in self.message_threads:
            self.message_threads[thread_id] = []
        self.message_threads[thread_id].append(message)
        
        # Add to recipient's inbox
        if to_agent not in self.agent_inboxes:
            self.agent_inboxes[to_agent] = []
        self.agent_inboxes[to_agent].append(message)
        
        return message
    
    def get_agent_inbox(self, agent_name: str, unread_only: bool = False) -> List[AgentMessage]:
        """Get all messages for an agent"""
        return self.agent_inboxes.get(agent_name, [])
    
    def get_thread(self, thread_id: str) -> List[AgentMessage]:
        """Get all messages in a thread"""
        return self.message_threads.get(thread_id, [])
    
    def create_task_review(self, task_id: str, agent_name: str, agent_role: str,
                          user_request: str) -> AgentTaskReview:
        """Create a complete review state for an agent task"""
        
        # Generate LLM response
        llm_prompt = f"As {agent_role}, analyze this request: {user_request}"
        llm_response = self.llm_system.generate(llm_prompt)
        llm_tokens = len(llm_response.split()) * 1.3  # Rough token estimate
        
        # Get Librarian interpretation
        try:
            import asyncio
            # Use the librarian's ask method
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            librarian_response = loop.run_until_complete(
                self.librarian.ask(user_request, context={})
            )
            loop.close()
            
            librarian_interpretation = librarian_response.message
            librarian_commands = librarian_response.suggested_commands
            librarian_confidence = librarian_response.confidence
        except Exception as e:
            # Fallback if librarian fails
            librarian_interpretation = f"Analyzing: {user_request}"
            librarian_commands = []
            librarian_confidence = 0.5
        
        # Create librarian_analysis dict for compatibility
        librarian_analysis = {
            'interpretation': librarian_interpretation,
            'command_chain': librarian_commands,
            'confidence': librarian_confidence
        }
        
        # Determine overall confidence level
        if librarian_confidence >= 0.95:
            confidence_level = ConfidenceLevel.GREEN
        elif librarian_confidence >= 0.70:
            confidence_level = ConfidenceLevel.YELLOW
        else:
            confidence_level = ConfidenceLevel.RED
        
        # Create decision gates
        gates = self._create_decision_gates(user_request, llm_response, librarian_analysis)
        
        # Calculate costs
        token_cost = int(llm_tokens)
        revenue_potential = self._estimate_revenue(user_request, llm_response)
        cost_benefit_ratio = revenue_potential / max(token_cost, 1)
        
        # Generate clarifying questions
        questions = self._generate_clarifying_questions(
            user_request, llm_response, librarian_confidence
        )
        
        # Create initial message thread
        initial_message = self.send_message(
            from_agent="System",
            to_agent=agent_name,
            message_type=MessageType.TASK_ASSIGNMENT,
            subject=f"New Task: {user_request[:50]}...",
            body=f"You have been assigned a new task. Please review and provide your analysis.",
            requires_response=True
        )
        
        review = AgentTaskReview(
            task_id=task_id,
            agent_name=agent_name,
            agent_role=agent_role,
            llm_state={
                'prompt': llm_prompt,
                'response': llm_response,
                'model': 'groq-llama-3.3-70b'
            },
            llm_prompt=llm_prompt,
            llm_response=llm_response,
            llm_tokens_used=token_cost,
            librarian_interpretation=librarian_interpretation,
            librarian_command_chain=librarian_commands,
            librarian_confidence=librarian_confidence,
            gates=gates,
            overall_confidence=confidence_level,
            token_cost=token_cost,
            revenue_potential=revenue_potential,
            cost_benefit_ratio=cost_benefit_ratio,
            questions=questions,
            message_thread=[initial_message]
        )
        
        self.task_reviews[task_id] = review
        return review
    
    def _create_decision_gates(self, request: str, llm_response: str, 
                              librarian_analysis: Dict) -> List[DecisionGate]:
        """Create decision gates for the task"""
        gates = []
        
        # Gate 1: Revenue vs Cost
        gates.append(DecisionGate(
            gate_id="revenue_gate",
            question="Does this task generate revenue or just cost tokens?",
            options=["Generates Revenue", "Costs Tokens Only", "Uncertain"],
            confidence=0.7,
            reasoning="Analyzing revenue potential based on task type",
            token_cost=100,
            revenue_impact=0.0
        ))
        
        # Gate 2: Information Source
        gates.append(DecisionGate(
            gate_id="info_source_gate",
            question="Where should information come from?",
            options=["Generate with AI", "Request from User", "Hire External Service"],
            confidence=0.8,
            reasoning="Determining optimal information source",
            token_cost=50,
            revenue_impact=0.0
        ))
        
        # Gate 3: Complexity Level
        gates.append(DecisionGate(
            gate_id="complexity_gate",
            question="What is the task complexity?",
            options=["Simple (Single Agent)", "Medium (Multiple Agents)", "Complex (Sub-Agents Required)"],
            confidence=0.75,
            reasoning="Assessing task complexity for resource allocation",
            token_cost=75,
            revenue_impact=0.0
        ))
        
        return gates
    
    def _estimate_revenue(self, request: str, llm_response: str) -> float:
        """Estimate revenue potential of a task"""
        # Simple heuristic - check for revenue-related keywords
        revenue_keywords = ['sell', 'product', 'customer', 'payment', 'price', 'revenue', 'profit']
        keyword_count = sum(1 for keyword in revenue_keywords if keyword in request.lower())
        
        # Estimate based on keyword presence
        if keyword_count >= 3:
            return 1000.0  # High revenue potential
        elif keyword_count >= 1:
            return 500.0  # Medium revenue potential
        else:
            return 0.0  # No direct revenue
    
    def _generate_clarifying_questions(self, request: str, llm_response: str, 
                                      confidence: float) -> List[Dict]:
        """Generate questions to boost confidence"""
        questions = []
        
        if confidence < 0.95:
            questions.append({
                'question': 'What is the specific deliverable format you need?',
                'reason': 'To increase confidence in output format',
                'confidence_boost': 0.1
            })
        
        if confidence < 0.85:
            questions.append({
                'question': 'What is your target audience or customer?',
                'reason': 'To tailor content appropriately',
                'confidence_boost': 0.1
            })
        
        if confidence < 0.75:
            questions.append({
                'question': 'What is your budget or timeline for this task?',
                'reason': 'To optimize resource allocation',
                'confidence_boost': 0.15
            })
        
        return questions
    
    def update_task_with_answer(self, task_id: str, question_index: int, 
                               answer: str) -> AgentTaskReview:
        """Update task review with answer to clarifying question"""
        review = self.task_reviews.get(task_id)
        if not review:
            return None
        
        # Send message about the answer
        self.send_message(
            from_agent="User",
            to_agent=review.agent_name,
            message_type=MessageType.ANSWER,
            subject=f"Answer to Question {question_index + 1}",
            body=answer,
            thread_id=review.message_thread[0].thread_id
        )
        
        # Regenerate with new information
        updated_prompt = f"{review.llm_prompt}\n\nAdditional Information: {answer}"
        new_llm_response = self.llm_system.generate(updated_prompt)
        
        # Update confidence
        review.librarian_confidence = min(review.librarian_confidence + 0.1, 1.0)
        
        # Update confidence level
        if review.librarian_confidence >= 0.95:
            review.overall_confidence = ConfidenceLevel.GREEN
        elif review.librarian_confidence >= 0.70:
            review.overall_confidence = ConfidenceLevel.YELLOW
        
        # Update LLM state
        review.llm_response = new_llm_response
        review.llm_state['response'] = new_llm_response
        
        return review
    
    def librarian_deliverable_communication(self, task_id: str, 
                                           deliverable_request: str) -> Dict:
        """Handle communication between Librarian and Deliverable Function"""
        
        # Librarian analyzes the request
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            librarian_response = loop.run_until_complete(
                self.librarian.ask(deliverable_request, context={})
            )
            loop.close()
            
            librarian_analysis = {
                'interpretation': librarian_response.message,
                'command_chain': librarian_response.suggested_commands,
                'confidence': librarian_response.confidence,
                'estimated_tokens': 1000,  # Estimate
                'revenue_potential': 0.0
            }
        except Exception as e:
            librarian_analysis = {
                'interpretation': f"Analyzing: {deliverable_request}",
                'command_chain': [],
                'confidence': 0.5,
                'estimated_tokens': 1000,
                'revenue_potential': 0.0
            }
        
        # Send message to Deliverable Function
        msg = self.send_message(
            from_agent="Librarian",
            to_agent="DeliverableFunction",
            message_type=MessageType.TASK_ASSIGNMENT,
            subject="Optimal Execution Plan",
            body=f"Best approach: {librarian_analysis.get('interpretation', '')}\n"
                 f"Command chain: {', '.join(librarian_analysis.get('command_chain', []))}\n"
                 f"Estimated cost: {librarian_analysis.get('estimated_tokens', 0)} tokens\n"
                 f"Revenue potential: ${librarian_analysis.get('revenue_potential', 0)}",
            requires_response=True,
            attachments=[{'analysis': librarian_analysis}]
        )
        
        # Deliverable Function responds with execution plan
        response_msg = self.send_message(
            from_agent="DeliverableFunction",
            to_agent="Librarian",
            message_type=MessageType.STATUS_UPDATE,
            subject="Execution Plan Confirmed",
            body=f"I will execute the following steps:\n"
                 f"1. {librarian_analysis.get('command_chain', ['No commands'])[0]}\n"
                 f"2. Monitor token usage\n"
                 f"3. Report back with results",
            thread_id=msg.thread_id
        )
        
        return {
            'librarian_message': msg.to_dict(),
            'deliverable_response': response_msg.to_dict(),
            'analysis': librarian_analysis
        }
    
    def get_task_review(self, task_id: str) -> Optional[AgentTaskReview]:
        """Get the complete review state for a task"""
        return self.task_reviews.get(task_id)
    
    def get_all_task_reviews(self) -> List[AgentTaskReview]:
        """Get all task reviews"""
        return list(self.task_reviews.values())

# Global communication hub instance
_communication_hub = None

def get_communication_hub(librarian=None, llm_system=None):
    """Get or create the global communication hub"""
    global _communication_hub
    if _communication_hub is None and librarian and llm_system:
        _communication_hub = AgentCommunicationHub(librarian, llm_system)
    return _communication_hub