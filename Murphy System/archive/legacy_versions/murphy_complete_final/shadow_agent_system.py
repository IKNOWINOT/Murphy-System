"""
Shadow Agent Learning System
Observes user actions, learns patterns, and proposes automations
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
from enum import Enum

class ObservationType(Enum):
    """Types of observations"""
    COMMAND = "command"
    STATE_CHANGE = "state_change"
    ARTIFACT_GENERATION = "artifact_generation"
    DOCUMENT_EDIT = "document_edit"
    APPROVAL = "approval"
    REJECTION = "rejection"

class ProposalStatus(Enum):
    """Status of automation proposals"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
    PAUSED = "paused"

class AutomationTrigger(Enum):
    """Types of automation triggers"""
    TIME_BASED = "time_based"
    EVENT_BASED = "event_based"
    PATTERN_BASED = "pattern_based"
    THRESHOLD_BASED = "threshold_based"

class Observation:
    """Represents a single observed action"""
    
    def __init__(self, obs_type: ObservationType, action: str, context: Dict):
        self.id = str(uuid.uuid4())
        self.type = obs_type
        self.action = action
        self.context = context
        self.timestamp = datetime.now().isoformat()
        self.user_id = context.get('user_id', 'default')
        self.session_id = context.get('session_id', 'default')
        
    def to_dict(self) -> Dict:
        """Convert observation to dictionary"""
        return {
            'id': self.id,
            'type': self.type.value,
            'action': self.action,
            'context': self.context,
            'timestamp': self.timestamp,
            'user_id': self.user_id,
            'session_id': self.session_id
        }

class Pattern:
    """Represents a detected pattern in user behavior"""
    
    def __init__(self, pattern_type: str, description: str, observations: List[Observation]):
        self.id = str(uuid.uuid4())
        self.type = pattern_type
        self.description = description
        self.observations = observations
        self.frequency = len(observations)
        self.confidence = 0.0
        self.first_seen = observations[0].timestamp if observations else datetime.now().isoformat()
        self.last_seen = observations[-1].timestamp if observations else datetime.now().isoformat()
        self.detected_at = datetime.now().isoformat()
        
    def calculate_confidence(self):
        """Calculate confidence score based on frequency and consistency"""
        # Base confidence on frequency
        if self.frequency < 3:
            self.confidence = 0.3
        elif self.frequency < 5:
            self.confidence = 0.5
        elif self.frequency < 10:
            self.confidence = 0.7
        else:
            self.confidence = 0.9
            
        # Adjust for time consistency
        if len(self.observations) >= 2:
            timestamps = [datetime.fromisoformat(obs.timestamp) for obs in self.observations]
            time_diffs = [(timestamps[i+1] - timestamps[i]).total_seconds() 
                         for i in range(len(timestamps)-1)]
            
            if time_diffs:
                avg_diff = sum(time_diffs) / len(time_diffs)
                std_dev = (sum((x - avg_diff) ** 2 for x in time_diffs) / len(time_diffs)) ** 0.5
                
                # More consistent timing = higher confidence
                if std_dev < avg_diff * 0.2:  # Very consistent
                    self.confidence = min(1.0, self.confidence + 0.1)
                    
    def to_dict(self) -> Dict:
        """Convert pattern to dictionary"""
        return {
            'id': self.id,
            'type': self.type,
            'description': self.description,
            'frequency': self.frequency,
            'confidence': self.confidence,
            'first_seen': self.first_seen,
            'last_seen': self.last_seen,
            'detected_at': self.detected_at,
            'observation_count': len(self.observations)
        }

class AutomationProposal:
    """Represents a proposed automation"""
    
    def __init__(self, pattern: Pattern, automation_type: str, description: str):
        self.id = str(uuid.uuid4())
        self.pattern_id = pattern.id
        self.type = automation_type
        self.description = description
        self.trigger = AutomationTrigger.PATTERN_BASED
        self.status = ProposalStatus.PENDING
        self.confidence = pattern.confidence
        self.created_at = datetime.now().isoformat()
        self.approved_at = None
        self.rejected_at = None
        self.rejection_reason = None
        self.execution_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.last_executed = None
        self.actions = []
        self.conditions = []
        
    def approve(self):
        """Approve the proposal"""
        self.status = ProposalStatus.APPROVED
        self.approved_at = datetime.now().isoformat()
        
    def reject(self, reason: str = None):
        """Reject the proposal"""
        self.status = ProposalStatus.REJECTED
        self.rejected_at = datetime.now().isoformat()
        self.rejection_reason = reason
        
    def activate(self):
        """Activate the automation"""
        if self.status == ProposalStatus.APPROVED:
            self.status = ProposalStatus.ACTIVE
            
    def pause(self):
        """Pause the automation"""
        if self.status == ProposalStatus.ACTIVE:
            self.status = ProposalStatus.PAUSED
            
    def record_execution(self, success: bool):
        """Record an execution result"""
        self.execution_count += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.last_executed = datetime.now().isoformat()
        
        # Update confidence based on success rate
        if self.execution_count > 0:
            success_rate = self.success_count / self.execution_count
            self.confidence = (self.confidence + success_rate) / 2
            
    def to_dict(self) -> Dict:
        """Convert proposal to dictionary"""
        return {
            'id': self.id,
            'pattern_id': self.pattern_id,
            'type': self.type,
            'description': self.description,
            'trigger': self.trigger.value,
            'status': self.status.value,
            'confidence': self.confidence,
            'created_at': self.created_at,
            'approved_at': self.approved_at,
            'rejected_at': self.rejected_at,
            'rejection_reason': self.rejection_reason,
            'execution_count': self.execution_count,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'last_executed': self.last_executed,
            'actions': self.actions,
            'conditions': self.conditions
        }

class ShadowAgent:
    """A shadow agent that observes and learns"""
    
    def __init__(self, name: str, domain: str):
        self.id = str(uuid.uuid4())
        self.name = name
        self.domain = domain
        self.observations = []
        self.patterns = []
        self.proposals = []
        self.active_automations = []
        self.learning_enabled = True
        self.created_at = datetime.now().isoformat()
        self.last_learning_cycle = None
        self.total_observations = 0
        self.total_patterns = 0
        self.total_proposals = 0
        
    def observe(self, obs_type: ObservationType, action: str, context: Dict):
        """Record an observation"""
        if not self.learning_enabled:
            return
            
        observation = Observation(obs_type, action, context)
        self.observations.append(observation)
        self.total_observations += 1
        
        # Limit observation history
        if len(self.observations) > 1000:
            self.observations = self.observations[-1000:]
            
    def analyze_patterns(self) -> List[Pattern]:
        """Analyze observations to detect patterns"""
        if len(self.observations) < 3:
            return []
            
        detected_patterns = []
        
        # Pattern 1: Repeated commands
        command_sequences = defaultdict(list)
        for obs in self.observations:
            if obs.type == ObservationType.COMMAND:
                command_sequences[obs.action].append(obs)
                
        for action, obs_list in command_sequences.items():
            if len(obs_list) >= 3:
                pattern = Pattern(
                    "repeated_command",
                    f"User frequently executes: {action}",
                    obs_list
                )
                pattern.calculate_confidence()
                detected_patterns.append(pattern)
                
        # Pattern 2: Command sequences
        if len(self.observations) >= 5:
            for i in range(len(self.observations) - 2):
                seq = [self.observations[i], self.observations[i+1], self.observations[i+2]]
                if all(obs.type == ObservationType.COMMAND for obs in seq):
                    seq_str = " → ".join([obs.action for obs in seq])
                    
                    # Check if this sequence appears multiple times
                    count = 0
                    for j in range(len(self.observations) - 2):
                        check_seq = [self.observations[j], self.observations[j+1], self.observations[j+2]]
                        check_str = " → ".join([obs.action for obs in check_seq])
                        if check_str == seq_str:
                            count += 1
                            
                    if count >= 2:
                        pattern = Pattern(
                            "command_sequence",
                            f"User often executes sequence: {seq_str}",
                            seq
                        )
                        pattern.frequency = count
                        pattern.calculate_confidence()
                        detected_patterns.append(pattern)
                        break  # Only detect first sequence
                        
        # Pattern 3: Time-based patterns
        time_based = defaultdict(list)
        for obs in self.observations:
            hour = datetime.fromisoformat(obs.timestamp).hour
            time_based[hour].append(obs)
            
        for hour, obs_list in time_based.items():
            if len(obs_list) >= 5:
                pattern = Pattern(
                    "time_based",
                    f"User is active around {hour}:00",
                    obs_list
                )
                pattern.calculate_confidence()
                detected_patterns.append(pattern)
                
        # Pattern 4: Artifact generation patterns
        artifact_types = defaultdict(list)
        for obs in self.observations:
            if obs.type == ObservationType.ARTIFACT_GENERATION:
                artifact_type = obs.context.get('artifact_type', 'unknown')
                artifact_types[artifact_type].append(obs)
                
        for art_type, obs_list in artifact_types.items():
            if len(obs_list) >= 3:
                pattern = Pattern(
                    "artifact_preference",
                    f"User frequently generates {art_type} artifacts",
                    obs_list
                )
                pattern.calculate_confidence()
                detected_patterns.append(pattern)
                
        self.patterns.extend(detected_patterns)
        self.total_patterns += len(detected_patterns)
        self.last_learning_cycle = datetime.now().isoformat()
        
        return detected_patterns
        
    def generate_proposals(self, patterns: List[Pattern]) -> List[AutomationProposal]:
        """Generate automation proposals from patterns"""
        new_proposals = []
        
        for pattern in patterns:
            if pattern.confidence < 0.5:
                continue  # Only propose high-confidence patterns
                
            proposal = None
            
            if pattern.type == "repeated_command":
                proposal = AutomationProposal(
                    pattern,
                    "command_automation",
                    f"Automate: {pattern.description}"
                )
                proposal.actions = [{'type': 'execute_command', 'command': pattern.observations[0].action}]
                proposal.trigger = AutomationTrigger.EVENT_BASED
                
            elif pattern.type == "command_sequence":
                proposal = AutomationProposal(
                    pattern,
                    "sequence_automation",
                    f"Automate sequence: {pattern.description}"
                )
                proposal.actions = [
                    {'type': 'execute_command', 'command': obs.action}
                    for obs in pattern.observations[:3]
                ]
                proposal.trigger = AutomationTrigger.PATTERN_BASED
                
            elif pattern.type == "time_based":
                proposal = AutomationProposal(
                    pattern,
                    "scheduled_automation",
                    f"Schedule tasks: {pattern.description}"
                )
                proposal.trigger = AutomationTrigger.TIME_BASED
                
            elif pattern.type == "artifact_preference":
                proposal = AutomationProposal(
                    pattern,
                    "artifact_automation",
                    f"Auto-generate artifacts: {pattern.description}"
                )
                proposal.trigger = AutomationTrigger.EVENT_BASED
                
            if proposal:
                self.proposals.append(proposal)
                new_proposals.append(proposal)
                self.total_proposals += 1
                
        return new_proposals
        
    def to_dict(self) -> Dict:
        """Convert shadow agent to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'domain': self.domain,
            'learning_enabled': self.learning_enabled,
            'created_at': self.created_at,
            'last_learning_cycle': self.last_learning_cycle,
            'total_observations': self.total_observations,
            'total_patterns': self.total_patterns,
            'total_proposals': self.total_proposals,
            'recent_observations': len(self.observations),
            'active_automations': len(self.active_automations)
        }

class ShadowAgentSystem:
    """Main system for managing shadow agents"""
    
    def __init__(self):
        self.agents: Dict[str, ShadowAgent] = {}
        self.global_observations = []
        self.global_patterns = []
        self.global_proposals = []
        
        # Create default shadow agents
        self._create_default_agents()
        
    def _create_default_agents(self):
        """Create default shadow agents for each domain"""
        domains = [
            ("Command Observer", "command_system"),
            ("Document Watcher", "living_documents"),
            ("Artifact Monitor", "artifact_generation"),
            ("State Tracker", "state_machine"),
            ("Workflow Analyzer", "workflows")
        ]
        
        for name, domain in domains:
            agent = ShadowAgent(name, domain)
            self.agents[agent.id] = agent
            
    def get_agent(self, agent_id: str) -> Optional[ShadowAgent]:
        """Get shadow agent by ID"""
        return self.agents.get(agent_id)
        
    def list_agents(self) -> List[Dict]:
        """List all shadow agents"""
        return [agent.to_dict() for agent in self.agents.values()]
        
    def observe(self, domain: str, obs_type: ObservationType, action: str, context: Dict):
        """Record observation across relevant agents"""
        self.global_observations.append({
            'domain': domain,
            'type': obs_type.value,
            'action': action,
            'context': context,
            'timestamp': datetime.now().isoformat()
        })
        
        # Distribute to relevant agents
        for agent in self.agents.values():
            if agent.domain == domain or agent.domain == "workflows":
                agent.observe(obs_type, action, context)
                
    def run_learning_cycle(self) -> Dict:
        """Run learning cycle across all agents"""
        results = {
            'agents_analyzed': 0,
            'patterns_detected': 0,
            'proposals_generated': 0,
            'timestamp': datetime.now().isoformat()
        }
        
        for agent in self.agents.values():
            if not agent.learning_enabled:
                continue
                
            # Analyze patterns
            patterns = agent.analyze_patterns()
            results['patterns_detected'] += len(patterns)
            
            # Generate proposals
            proposals = agent.generate_proposals(patterns)
            results['proposals_generated'] += len(proposals)
            
            results['agents_analyzed'] += 1
            
            # Add to global collections
            self.global_patterns.extend(patterns)
            self.global_proposals.extend(proposals)
            
        return results
        
    def get_pending_proposals(self) -> List[Dict]:
        """Get all pending automation proposals"""
        pending = []
        for agent in self.agents.values():
            for proposal in agent.proposals:
                if proposal.status == ProposalStatus.PENDING:
                    pending.append({
                        'agent_id': agent.id,
                        'agent_name': agent.name,
                        **proposal.to_dict()
                    })
        return pending
        
    def approve_proposal(self, agent_id: str, proposal_id: str) -> bool:
        """Approve an automation proposal"""
        agent = self.agents.get(agent_id)
        if not agent:
            return False
            
        for proposal in agent.proposals:
            if proposal.id == proposal_id:
                proposal.approve()
                proposal.activate()
                agent.active_automations.append(proposal)
                return True
        return False
        
    def reject_proposal(self, agent_id: str, proposal_id: str, reason: str = None) -> bool:
        """Reject an automation proposal"""
        agent = self.agents.get(agent_id)
        if not agent:
            return False
            
        for proposal in agent.proposals:
            if proposal.id == proposal_id:
                proposal.reject(reason)
                return True
        return False
        
    def get_active_automations(self) -> List[Dict]:
        """Get all active automations"""
        active = []
        for agent in self.agents.values():
            for automation in agent.active_automations:
                if automation.status == ProposalStatus.ACTIVE:
                    active.append({
                        'agent_id': agent.id,
                        'agent_name': agent.name,
                        **automation.to_dict()
                    })
        return active
        
    def get_statistics(self) -> Dict:
        """Get system statistics"""
        total_observations = sum(agent.total_observations for agent in self.agents.values())
        total_patterns = sum(agent.total_patterns for agent in self.agents.values())
        total_proposals = sum(agent.total_proposals for agent in self.agents.values())
        
        pending_proposals = len(self.get_pending_proposals())
        active_automations = len(self.get_active_automations())
        
        return {
            'total_agents': len(self.agents),
            'total_observations': total_observations,
            'total_patterns': total_patterns,
            'total_proposals': total_proposals,
            'pending_proposals': pending_proposals,
            'active_automations': active_automations,
            'learning_enabled_agents': sum(1 for a in self.agents.values() if a.learning_enabled)
        }