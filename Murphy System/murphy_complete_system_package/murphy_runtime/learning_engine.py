# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Learning Engine
Advanced pattern detection and automation opportunity identification
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter
import re

class LearningEngine:
    """Advanced learning algorithms for pattern detection"""
    
    def __init__(self):
        self.pattern_cache = {}
        self.correlation_matrix = defaultdict(lambda: defaultdict(int))
        self.frequency_table = defaultdict(int)
        self.time_series_data = defaultdict(list)
        
    def detect_frequency_patterns(self, observations: List[Dict], 
                                  min_frequency: int = 3) -> List[Dict]:
        """Detect patterns based on action frequency"""
        patterns = []
        action_counts = Counter()
        action_observations = defaultdict(list)
        
        for obs in observations:
            action = obs.get('action', '')
            action_counts[action] += 1
            action_observations[action].append(obs)
            
        for action, count in action_counts.items():
            if count >= min_frequency:
                patterns.append({
                    'type': 'frequency',
                    'action': action,
                    'frequency': count,
                    'confidence': min(count / 10.0, 1.0),
                    'observations': action_observations[action],
                    'description': f"Action '{action}' occurs {count} times"
                })
                
        return patterns
        
    def detect_sequence_patterns(self, observations: List[Dict],
                                sequence_length: int = 3,
                                min_occurrences: int = 2) -> List[Dict]:
        """Detect recurring sequences of actions"""
        patterns = []
        sequences = defaultdict(list)
        
        # Extract action sequences
        for i in range(len(observations) - sequence_length + 1):
            seq = tuple(obs.get('action', '') for obs in observations[i:i+sequence_length])
            sequences[seq].append(observations[i:i+sequence_length])
            
        # Find recurring sequences
        for seq, occurrences in sequences.items():
            if len(occurrences) >= min_occurrences:
                patterns.append({
                    'type': 'sequence',
                    'sequence': list(seq),
                    'occurrences': len(occurrences),
                    'confidence': min(len(occurrences) / 5.0, 1.0),
                    'observations': occurrences[0],  # First occurrence
                    'description': f"Sequence {' → '.join(seq)} occurs {len(occurrences)} times"
                })
                
        return patterns
        
    def detect_temporal_patterns(self, observations: List[Dict]) -> List[Dict]:
        """Detect time-based patterns"""
        patterns = []
        hourly_actions = defaultdict(list)
        daily_actions = defaultdict(list)
        
        for obs in observations:
            timestamp = obs.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    hour = dt.hour
                    day = dt.strftime('%A')
                    
                    hourly_actions[hour].append(obs)
                    daily_actions[day].append(obs)
                except:
                    continue
                    
        # Hourly patterns
        for hour, obs_list in hourly_actions.items():
            if len(obs_list) >= 3:
                patterns.append({
                    'type': 'temporal_hourly',
                    'hour': hour,
                    'count': len(obs_list),
                    'confidence': min(len(obs_list) / 10.0, 1.0),
                    'observations': obs_list,
                    'description': f"High activity at {hour}:00 ({len(obs_list)} actions)"
                })
                
        # Daily patterns
        for day, obs_list in daily_actions.items():
            if len(obs_list) >= 5:
                patterns.append({
                    'type': 'temporal_daily',
                    'day': day,
                    'count': len(obs_list),
                    'confidence': min(len(obs_list) / 20.0, 1.0),
                    'observations': obs_list,
                    'description': f"High activity on {day} ({len(obs_list)} actions)"
                })
                
        return patterns
        
    def detect_context_patterns(self, observations: List[Dict]) -> List[Dict]:
        """Detect patterns based on context"""
        patterns = []
        context_groups = defaultdict(list)
        
        for obs in observations:
            context = obs.get('context', {})
            
            # Group by domain
            domain = context.get('domain', 'unknown')
            context_groups[f"domain:{domain}"].append(obs)
            
            # Group by document type
            doc_type = context.get('document_type', None)
            if doc_type:
                context_groups[f"doc_type:{doc_type}"].append(obs)
                
            # Group by artifact type
            artifact_type = context.get('artifact_type', None)
            if artifact_type:
                context_groups[f"artifact:{artifact_type}"].append(obs)
                
        for group_key, obs_list in context_groups.items():
            if len(obs_list) >= 3:
                patterns.append({
                    'type': 'context',
                    'context_key': group_key,
                    'count': len(obs_list),
                    'confidence': min(len(obs_list) / 10.0, 1.0),
                    'observations': obs_list,
                    'description': f"Frequent actions in context: {group_key}"
                })
                
        return patterns
        
    def detect_correlation_patterns(self, observations: List[Dict]) -> List[Dict]:
        """Detect correlated actions"""
        patterns = []
        
        # Build correlation matrix
        for i in range(len(observations) - 1):
            action1 = observations[i].get('action', '')
            action2 = observations[i + 1].get('action', '')
            
            if action1 and action2:
                self.correlation_matrix[action1][action2] += 1
                
        # Find strong correlations
        for action1, correlations in self.correlation_matrix.items():
            for action2, count in correlations.items():
                if count >= 3:
                    patterns.append({
                        'type': 'correlation',
                        'action1': action1,
                        'action2': action2,
                        'correlation_count': count,
                        'confidence': min(count / 10.0, 1.0),
                        'description': f"'{action1}' often followed by '{action2}' ({count} times)"
                    })
                    
        return patterns
        
    def identify_automation_opportunities(self, patterns: List[Dict]) -> List[Dict]:
        """Identify automation opportunities from patterns"""
        opportunities = []
        
        for pattern in patterns:
            opportunity = None
            
            if pattern['type'] == 'frequency' and pattern['confidence'] >= 0.7:
                opportunity = {
                    'type': 'command_shortcut',
                    'pattern_id': id(pattern),
                    'description': f"Create shortcut for frequently used command: {pattern['action']}",
                    'benefit': 'Reduce repetitive typing',
                    'confidence': pattern['confidence'],
                    'automation_type': 'keyboard_shortcut',
                    'estimated_time_saved': f"{pattern['frequency'] * 5} seconds per session"
                }
                
            elif pattern['type'] == 'sequence' and pattern['confidence'] >= 0.6:
                opportunity = {
                    'type': 'workflow_automation',
                    'pattern_id': id(pattern),
                    'description': f"Automate command sequence: {' → '.join(pattern['sequence'])}",
                    'benefit': 'Execute multiple commands with one action',
                    'confidence': pattern['confidence'],
                    'automation_type': 'macro',
                    'estimated_time_saved': f"{len(pattern['sequence']) * 10} seconds per execution"
                }
                
            elif pattern['type'] == 'temporal_hourly' and pattern['confidence'] >= 0.7:
                opportunity = {
                    'type': 'scheduled_task',
                    'pattern_id': id(pattern),
                    'description': f"Schedule tasks for {pattern['hour']}:00",
                    'benefit': 'Automatic execution at optimal time',
                    'confidence': pattern['confidence'],
                    'automation_type': 'cron_job',
                    'estimated_time_saved': 'Hands-free operation'
                }
                
            elif pattern['type'] == 'context' and pattern['confidence'] >= 0.6:
                opportunity = {
                    'type': 'context_automation',
                    'pattern_id': id(pattern),
                    'description': f"Auto-trigger actions in context: {pattern['context_key']}",
                    'benefit': 'Context-aware automation',
                    'confidence': pattern['confidence'],
                    'automation_type': 'event_trigger',
                    'estimated_time_saved': 'Proactive assistance'
                }
                
            elif pattern['type'] == 'correlation' and pattern['confidence'] >= 0.7:
                opportunity = {
                    'type': 'predictive_suggestion',
                    'pattern_id': id(pattern),
                    'description': f"Suggest '{pattern['action2']}' after '{pattern['action1']}'",
                    'benefit': 'Predictive command suggestions',
                    'confidence': pattern['confidence'],
                    'automation_type': 'suggestion',
                    'estimated_time_saved': 'Faster workflow'
                }
                
            if opportunity:
                opportunities.append(opportunity)
                
        return opportunities
        
    def calculate_pattern_strength(self, pattern: Dict) -> float:
        """Calculate overall pattern strength"""
        confidence = pattern.get('confidence', 0.0)
        frequency = pattern.get('frequency', pattern.get('count', 0))
        
        # Base score on confidence
        strength = confidence
        
        # Boost for high frequency
        if frequency >= 10:
            strength = min(1.0, strength + 0.1)
        elif frequency >= 20:
            strength = min(1.0, strength + 0.2)
            
        # Boost for recent activity
        observations = pattern.get('observations', [])
        if observations:
            try:
                last_obs = observations[-1]
                timestamp = last_obs.get('timestamp', '')
                if timestamp:
                    dt = datetime.fromisoformat(timestamp)
                    age_hours = (datetime.now() - dt).total_seconds() / 3600
                    
                    if age_hours < 24:  # Very recent
                        strength = min(1.0, strength + 0.1)
            except:
                pass
                
        return strength
        
    def rank_patterns(self, patterns: List[Dict]) -> List[Dict]:
        """Rank patterns by strength and relevance"""
        for pattern in patterns:
            pattern['strength'] = self.calculate_pattern_strength(pattern)
            
        # Sort by strength descending
        return sorted(patterns, key=lambda p: p['strength'], reverse=True)
        
    def filter_noise(self, patterns: List[Dict], 
                    min_confidence: float = 0.5) -> List[Dict]:
        """Filter out low-confidence patterns"""
        return [p for p in patterns if p.get('confidence', 0) >= min_confidence]
        
    def merge_similar_patterns(self, patterns: List[Dict]) -> List[Dict]:
        """Merge similar patterns to reduce duplication"""
        merged = []
        seen = set()
        
        for pattern in patterns:
            # Create signature for pattern
            if pattern['type'] == 'frequency':
                sig = f"freq:{pattern['action']}"
            elif pattern['type'] == 'sequence':
                sig = f"seq:{'_'.join(pattern['sequence'])}"
            elif pattern['type'] == 'temporal_hourly':
                sig = f"time_h:{pattern['hour']}"
            elif pattern['type'] == 'temporal_daily':
                sig = f"time_d:{pattern['day']}"
            elif pattern['type'] == 'context':
                sig = f"ctx:{pattern['context_key']}"
            elif pattern['type'] == 'correlation':
                sig = f"corr:{pattern['action1']}_{pattern['action2']}"
            else:
                sig = f"other:{id(pattern)}"
                
            if sig not in seen:
                seen.add(sig)
                merged.append(pattern)
                
        return merged
        
    def analyze_comprehensive(self, observations: List[Dict]) -> Dict:
        """Run comprehensive analysis on observations"""
        all_patterns = []
        
        # Run all detection algorithms
        all_patterns.extend(self.detect_frequency_patterns(observations))
        all_patterns.extend(self.detect_sequence_patterns(observations))
        all_patterns.extend(self.detect_temporal_patterns(observations))
        all_patterns.extend(self.detect_context_patterns(observations))
        all_patterns.extend(self.detect_correlation_patterns(observations))
        
        # Filter and merge
        filtered = self.filter_noise(all_patterns)
        merged = self.merge_similar_patterns(filtered)
        ranked = self.rank_patterns(merged)
        
        # Identify opportunities
        opportunities = self.identify_automation_opportunities(ranked)
        
        return {
            'total_patterns': len(all_patterns),
            'filtered_patterns': len(filtered),
            'unique_patterns': len(merged),
            'patterns': ranked[:20],  # Top 20 patterns
            'automation_opportunities': opportunities,
            'analysis_timestamp': datetime.now().isoformat()
        }