"""
Input parsers and ingestors for organizational data

Supports:
- Org charts (CSV/JSON)
- Process flows (JSON/tagged text)
- SOP documents (text artifacts)
- Ticket events
- Email/thread summaries
"""

import csv
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .schemas import (
    ArtifactType,
    AuthorityLevel,
    HandoffEvent,
    OrgChartNode,
    ProcessFlow,
    WorkArtifact,
)

logger = logging.getLogger(__name__)


class OrgChartParser:
    """
    Parse organizational chart data from CSV or JSON

    CSV Format:
    node_id,role_name,reports_to,team,department,authority_level

    JSON Format:
    [
        {
            "node_id": "...",
            "role_name": "...",
            "reports_to": "...",
            "team": "...",
            "department": "...",
            "authority_level": "..."
        }
    ]
    """

    @staticmethod
    def parse_csv(file_path: str) -> List[OrgChartNode]:
        """Parse org chart from CSV file"""
        nodes = []

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                node = OrgChartNode(
                    node_id=row['node_id'],
                    role_name=row['role_name'],
                    reports_to=row.get('reports_to') or None,
                    team=row['team'],
                    department=row['department'],
                    authority_level=AuthorityLevel(row['authority_level']),
                    metadata={}
                )
                nodes.append(node)

        # Build direct_reports relationships
        OrgChartParser._build_relationships(nodes)

        return nodes

    @staticmethod
    def parse_json(file_path: str) -> List[OrgChartNode]:
        """Parse org chart from JSON file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        nodes = []
        for item in data:
            node = OrgChartNode(
                node_id=item['node_id'],
                role_name=item['role_name'],
                reports_to=item.get('reports_to'),
                team=item['team'],
                department=item['department'],
                authority_level=AuthorityLevel(item['authority_level']),
                metadata=item.get('metadata', {})
            )
            nodes.append(node)

        # Build direct_reports relationships
        OrgChartParser._build_relationships(nodes)

        return nodes

    @staticmethod
    def _build_relationships(nodes: List[OrgChartNode]):
        """Build direct_reports relationships"""
        node_map = {n.node_id: n for n in nodes}

        for node in nodes:
            if node.reports_to and node.reports_to in node_map:
                manager = node_map[node.reports_to]
                if node.node_id not in manager.direct_reports:
                    manager.direct_reports.append(node.node_id)


class ProcessFlowParser:
    """
    Parse process flow diagrams from JSON or tagged text

    JSON Format:
    {
        "flow_id": "...",
        "flow_name": "...",
        "steps": [
            {
                "step_id": "...",
                "role": "...",
                "action": "...",
                "inputs": [...],
                "outputs": [...]
            }
        ],
        "decision_points": [...],
        "handoffs": [...],
        "sla_targets": {...},
        "compliance_checkpoints": [...]
    }
    """

    @staticmethod
    def parse_json(file_path: str) -> ProcessFlow:
        """Parse process flow from JSON file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return ProcessFlow(
            flow_id=data['flow_id'],
            flow_name=data['flow_name'],
            steps=data['steps'],
            decision_points=data.get('decision_points', []),
            handoffs=data.get('handoffs', []),
            sla_targets=data.get('sla_targets', {}),
            compliance_checkpoints=data.get('compliance_checkpoints', [])
        )

    @staticmethod
    def parse_tagged_text(text: str) -> ProcessFlow:
        """
        Parse process flow from tagged text format

        Format:
        FLOW: flow_name
        STEP: step_id | role | action | inputs | outputs
        DECISION: decision_id | condition | true_path | false_path
        HANDOFF: from_role -> to_role | artifact
        SLA: metric = value
        COMPLIANCE: checkpoint_name
        """
        lines = text.strip().split('\n')

        flow_id = None
        flow_name = None
        steps = []
        decision_points = []
        handoffs = []
        sla_targets = {}
        compliance_checkpoints = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if line.startswith('FLOW:'):
                flow_name = line.split(':', 1)[1].strip()
                flow_id = flow_name.lower().replace(' ', '_')

            elif line.startswith('STEP:'):
                parts = [p.strip() for p in line.split(':', 1)[1].split('|')]
                if len(parts) >= 3:
                    steps.append({
                        'step_id': parts[0],
                        'role': parts[1],
                        'action': parts[2],
                        'inputs': parts[3].split(',') if len(parts) > 3 else [],
                        'outputs': parts[4].split(',') if len(parts) > 4 else []
                    })

            elif line.startswith('DECISION:'):
                parts = [p.strip() for p in line.split(':', 1)[1].split('|')]
                if len(parts) >= 3:
                    decision_points.append({
                        'decision_id': parts[0],
                        'condition': parts[1],
                        'true_path': parts[2],
                        'false_path': parts[3] if len(parts) > 3 else None
                    })

            elif line.startswith('HANDOFF:'):
                parts = line.split(':', 1)[1].strip().split('|')
                roles = parts[0].strip().split('->')
                if len(roles) == 2:
                    handoffs.append({
                        'from_role': roles[0].strip(),
                        'to_role': roles[1].strip(),
                        'artifact': parts[1].strip() if len(parts) > 1 else None
                    })

            elif line.startswith('SLA:'):
                parts = line.split(':', 1)[1].strip().split('=')
                if len(parts) == 2:
                    sla_targets[parts[0].strip()] = float(parts[1].strip())

            elif line.startswith('COMPLIANCE:'):
                checkpoint = line.split(':', 1)[1].strip()
                compliance_checkpoints.append(checkpoint)

        if not flow_id or not flow_name:
            raise ValueError("Process flow must have FLOW: declaration")

        return ProcessFlow(
            flow_id=flow_id,
            flow_name=flow_name,
            steps=steps,
            decision_points=decision_points,
            handoffs=handoffs,
            sla_targets=sla_targets,
            compliance_checkpoints=compliance_checkpoints
        )


class SOPDocumentParser:
    """
    Parse Standard Operating Procedure documents

    Extracts:
    - Responsibilities
    - Decision points
    - Approval requirements
    - Compliance requirements
    - Escalation procedures
    """

    @staticmethod
    def parse(text: str) -> Dict[str, any]:
        """
        Parse SOP document and extract structured information

        Returns:
            Dict with keys: responsibilities, decisions, approvals, compliance, escalations
        """
        result = {
            'responsibilities': [],
            'decisions': [],
            'approvals': [],
            'compliance': [],
            'escalations': []
        }

        # Extract responsibilities (lines starting with "Responsible for", "Must", "Shall")
        responsibility_patterns = [
            r'(?:Responsible for|Must|Shall)\s+(.+?)(?:\.|$)',
            r'(?:The role|This position)\s+(?:is responsible for|must|shall)\s+(.+?)(?:\.|$)'
        ]

        for pattern in responsibility_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                responsibility = match.group(1).strip()
                if responsibility and responsibility not in result['responsibilities']:
                    result['responsibilities'].append(responsibility)

        # Extract decision points (lines with "decide", "determine", "approve")
        decision_patterns = [
            r'(?:Decide|Determine|Approve)\s+(.+?)(?:\.|$)',
            r'(?:Decision|Approval)\s+(?:required|needed)\s+for\s+(.+?)(?:\.|$)'
        ]

        for pattern in decision_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                decision = match.group(1).strip()
                if decision and decision not in result['decisions']:
                    result['decisions'].append(decision)

        # Extract approval requirements
        approval_patterns = [
            r'(?:Requires|Needs)\s+approval\s+(?:from|by)\s+(.+?)(?:\.|$)',
            r'(?:Must be approved by)\s+(.+?)(?:\.|$)'
        ]

        for pattern in approval_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                approval = match.group(1).strip()
                if approval and approval not in result['approvals']:
                    result['approvals'].append(approval)

        # Extract compliance requirements (SOX, HIPAA, GDPR, etc.)
        compliance_patterns = [
            r'(SOX|HIPAA|GDPR|PCI-DSS|ISO\s+\d+)\s+(?:compliance|requirement|regulation)',
            r'(?:Comply with|Must comply with|Subject to)\s+(.+?)\s+(?:regulation|requirement)'
        ]

        for pattern in compliance_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                compliance = match.group(1).strip()
                if compliance and compliance not in result['compliance']:
                    result['compliance'].append(compliance)

        # Extract escalation procedures
        escalation_patterns = [
            r'Escalate\s+to\s+(.+?)(?:\.|$)',
            r'(?:If|When)\s+.+?\s+escalate\s+to\s+(.+?)(?:\.|$)'
        ]

        for pattern in escalation_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                escalation = match.group(1).strip()
                if escalation and escalation not in result['escalations']:
                    result['escalations'].append(escalation)

        return result


class TicketEventIngestor:
    """
    Ingest ticket/task events and convert to HandoffEvent artifacts

    Expected format:
    {
        "ticket_id": "...",
        "from_role": "...",
        "to_role": "...",
        "timestamp": "...",
        "action": "...",
        "duration_hours": ...,
        "approval_required": ...,
        "approval_granted": ...,
        "notes": "..."
    }
    """

    @staticmethod
    def ingest_json(file_path: str) -> List[HandoffEvent]:
        """Ingest ticket events from JSON file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        events = []
        for item in data:
            # Create work artifact
            artifact = WorkArtifact(
                artifact_id=item['ticket_id'],
                artifact_type=ArtifactType.TICKET,
                producer_role=item['from_role'],
                consumer_roles=[item['to_role']],
                content_hash=item.get('content_hash', ''),
                metadata={'action': item.get('action', '')}
            )

            # Create handoff event
            event = HandoffEvent(
                event_id=f"{item['ticket_id']}_handoff",
                from_role=item['from_role'],
                to_role=item['to_role'],
                artifact=artifact,
                timestamp=datetime.fromisoformat(item['timestamp']),
                duration_hours=item.get('duration_hours'),
                approval_required=item.get('approval_required', False),
                approval_granted=item.get('approval_granted'),
                notes=item.get('notes')
            )
            events.append(event)

        return events

    @staticmethod
    def ingest_csv(file_path: str) -> List[HandoffEvent]:
        """Ingest ticket events from CSV file"""
        events = []

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Create work artifact
                artifact = WorkArtifact(
                    artifact_id=row['ticket_id'],
                    artifact_type=ArtifactType.TICKET,
                    producer_role=row['from_role'],
                    consumer_roles=[row['to_role']],
                    content_hash=row.get('content_hash', ''),
                    metadata={'action': row.get('action', '')}
                )

                # Create handoff event
                event = HandoffEvent(
                    event_id=f"{row['ticket_id']}_handoff",
                    from_role=row['from_role'],
                    to_role=row['to_role'],
                    artifact=artifact,
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    duration_hours=float(row['duration_hours']) if row.get('duration_hours') else None,
                    approval_required=row.get('approval_required', '').lower() == 'true',
                    approval_granted=row.get('approval_granted', '').lower() == 'true' if row.get('approval_granted') else None,
                    notes=row.get('notes')
                )
                events.append(event)

        return events


class EmailThreadIngestor:
    """
    Ingest email/thread summaries and extract work patterns

    Expected format:
    {
        "thread_id": "...",
        "participants": [...],
        "timestamp": "...",
        "summary": "...",
        "decisions_made": [...],
        "action_items": [...],
        "approvals": [...]
    }
    """

    @staticmethod
    def ingest_json(file_path: str) -> List[WorkArtifact]:
        """Ingest email threads from JSON file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        artifacts = []
        for item in data:
            artifact = WorkArtifact(
                artifact_id=item['thread_id'],
                artifact_type=ArtifactType.EMAIL,
                producer_role=item['participants'][0] if item['participants'] else 'unknown',
                consumer_roles=item['participants'][1:] if len(item['participants']) > 1 else [],
                content_hash='',  # Would compute from summary
                metadata={
                    'summary': item.get('summary', ''),
                    'decisions_made': item.get('decisions_made', []),
                    'action_items': item.get('action_items', []),
                    'approvals': item.get('approvals', [])
                },
                created_at=datetime.fromisoformat(item['timestamp'])
            )
            artifacts.append(artifact)

        return artifacts


class DocumentIngestor:
    """
    Generic document ingestor for employment contracts, position descriptions, etc.

    Extracts:
    - Role responsibilities
    - Authority levels
    - Reporting structure
    - Compliance requirements
    """

    @staticmethod
    def ingest_text(text: str, doc_type: str = "employment_contract") -> Dict[str, any]:
        """
        Ingest document text and extract structured information

        Args:
            text: Document text
            doc_type: Type of document (employment_contract, position_description, etc.)

        Returns:
            Dict with extracted information
        """
        result = {
            'doc_type': doc_type,
            'responsibilities': [],
            'authority_level': None,
            'reports_to': None,
            'compliance_requirements': [],
            'decision_authority': [],
            'escalation_paths': []
        }

        # Use SOP parser for responsibilities
        sop_data = SOPDocumentParser.parse(text)
        result['responsibilities'] = sop_data['responsibilities']
        result['compliance_requirements'] = sop_data['compliance']
        result['escalation_paths'] = sop_data['escalations']
        result['decision_authority'] = sop_data['decisions']

        # Extract reporting structure
        reports_to_pattern = r'(?:Reports to|Reporting to)\s+(.+?)(?:\.|$)'
        match = re.search(reports_to_pattern, text, re.IGNORECASE)
        if match:
            result['reports_to'] = match.group(1).strip()

        # Extract authority level
        authority_patterns = [
            r'(?:Authority level|Decision authority):\s*(\w+)',
            r'(?:Has|Granted)\s+(\w+)\s+authority'
        ]
        for pattern in authority_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                authority = match.group(1).strip().lower()
                result['authority_level'] = authority
                break

        return result
