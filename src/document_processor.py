"""
Design Document Processing System
Handles uploaded design documents, equipment selection, and trigger generation
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("document_processor")


class DocumentType(Enum):
    """Types of documents"""
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    ARCHITECTURE = "architecture"
    SPECIFICATION = "specification"
    EQUIPMENT_LIST = "equipment_list"
    TECHNICAL = "technical"
    BUSINESS = "business"


class DocumentStatus(Enum):
    """Document processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    VALIDATED = "validated"
    ERROR = "error"


@dataclass
class DocumentMetadata:
    """Metadata for uploaded document"""
    document_id: str
    name: str
    file_type: str
    size: int
    uploaded_at: str
    document_type: DocumentType
    status: DocumentStatus
    checksum: str
    version: str = "1.0"

    def to_dict(self) -> Dict:
        return {
            "document_id": self.document_id,
            "name": self.name,
            "file_type": self.file_type,
            "size": self.size,
            "uploaded_at": self.uploaded_at,
            "document_type": self.document_type.value,
            "status": self.status.value,
            "checksum": self.checksum,
            "version": self.version
        }


@dataclass
class DesignRequirement:
    """Extracted design requirement"""
    requirement_id: str
    text: str
    category: str  # functional, non_functional, constraint, quality
    priority: str  # critical, high, medium, low
    source: str  # document_id and location
    artifacts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "requirement_id": self.requirement_id,
            "text": self.text,
            "category": self.category,
            "priority": self.priority,
            "source": self.source,
            "artifacts": self.artifacts
        }


@dataclass
class EquipmentSelection:
    """Selected equipment/component"""
    equipment_id: str
    name: str
    type: str  # hardware, software, service, platform
    specifications: Dict[str, Any]
    quantity: int
    cost: float
    vendor: Optional[str] = None
    alternatives: List[str] = field(default_factory=list)
    justification: str = ""

    def to_dict(self) -> Dict:
        return {
            "equipment_id": self.equipment_id,
            "name": self.name,
            "type": self.type,
            "specifications": self.specifications,
            "quantity": self.quantity,
            "cost": self.cost,
            "vendor": self.vendor,
            "alternatives": self.alternatives,
            "justification": self.justification
        }


@dataclass
class SystemTrigger:
    """Trigger for system action"""
    trigger_id: str
    name: str
    trigger_type: str  # condition, event, time, user_action
    condition: str
    action: str
    parameters: Dict[str, Any]
    priority: int
    enabled: bool = True
    created_from: Optional[str] = None  # document_id if from document

    def to_dict(self) -> Dict:
        return {
            "trigger_id": self.trigger_id,
            "name": self.name,
            "trigger_type": self.trigger_type,
            "condition": self.condition,
            "action": self.action,
            "parameters": self.parameters,
            "priority": self.priority,
            "enabled": self.enabled,
            "created_from": self.created_from
        }


class DocumentProcessor:
    """
    Processes design documents, extracts requirements, selects equipment, generates triggers
    """

    def __init__(self):
        self.documents: Dict[str, DocumentMetadata] = {}
        self.requirements: Dict[str, DesignRequirement] = {}
        self.equipment: Dict[str, EquipmentSelection] = {}
        self.triggers: Dict[str, SystemTrigger] = {}
        self.document_count = 0
        self.requirement_count = 0
        self.equipment_count = 0
        self.trigger_count = 0

        # Equipment catalog (simplified - would be database in production)
        self.equipment_catalog = self._load_equipment_catalog()

        # Trigger templates
        self.trigger_templates = self._load_trigger_templates()

    def _load_equipment_catalog(self) -> Dict[str, Dict]:
        """Load equipment catalog with available options"""
        return {
            "hardware": {
                "servers": [
                    {
                        "name": "AWS EC2 t3.large",
                        "specifications": {"cpu": 2, "ram": "8GB", "storage": "100GB SSD"},
                        "cost_per_hour": 0.0833
                    },
                    {
                        "name": "AWS EC2 c5.2xlarge",
                        "specifications": {"cpu": 8, "ram": "16GB", "storage": "100GB SSD"},
                        "cost_per_hour": 0.34
                    },
                    {
                        "name": "GCP n2-standard-4",
                        "specifications": {"cpu": 4, "ram": "16GB", "storage": "100GB SSD"},
                        "cost_per_hour": 0.1875
                    }
                ],
                "databases": [
                    {
                        "name": "AWS RDS PostgreSQL",
                        "specifications": {"type": "PostgreSQL", "version": "14", "ram": "4GB"},
                        "cost_per_hour": 0.15
                    },
                    {
                        "name": "Google Cloud SQL",
                        "specifications": {"type": "MySQL", "version": "8.0", "ram": "4GB"},
                        "cost_per_hour": 0.12
                    }
                ]
            },
            "software": {
                "frameworks": [
                    {
                        "name": "React",
                        "specifications": {"type": "frontend", "language": "JavaScript"},
                        "cost": 0  # Open source
                    },
                    {
                        "name": "Node.js",
                        "specifications": {"type": "backend", "language": "JavaScript"},
                        "cost": 0  # Open source
                    },
                    {
                        "name": "Django",
                        "specifications": {"type": "backend", "language": "Python"},
                        "cost": 0  # Open source
                    }
                ],
                "databases": [
                    {
                        "name": "PostgreSQL",
                        "specifications": {"type": "relational", "open_source": True},
                        "cost": 0  # Open source
                    },
                    {
                        "name": "MongoDB",
                        "specifications": {"type": "document", "open_source": True},
                        "cost": 0  # Community edition
                    }
                ]
            },
            "services": {
                "monitoring": [
                    {
                        "name": "Datadog",
                        "specifications": {"type": "apm", "features": ["metrics", "logs", "traces"]},
                        "cost_per_hour": 0.20
                    },
                    {
                        "name": "Prometheus + Grafana",
                        "specifications": {"type": "self_hosted", "features": ["metrics", "visualization"]},
                        "cost": 0  # Open source
                    }
                ],
                "cdn": [
                    {
                        "name": "Cloudflare",
                        "specifications": {"type": "cdn", "features": ["ddos_protection", "ssl"]},
                        "cost_per_hour": 0.05
                    },
                    {
                        "name": "AWS CloudFront",
                        "specifications": {"type": "cdn", "features": ["edge_locations", "ssl"]},
                        "cost_per_hour": 0.085
                    }
                ]
            }
        }

    def _load_trigger_templates(self) -> Dict[str, Dict]:
        """Load trigger templates for common scenarios"""
        return {
            "deployment": {
                "name": "deployment_trigger",
                "trigger_type": "event",
                "condition": "build_completed",
                "action": "deploy_to_staging",
                "parameters": {"environment": "staging"}
            },
            "scaling": {
                "name": "auto_scale_trigger",
                "trigger_type": "condition",
                "condition": "cpu_usage > 80%",
                "action": "scale_up",
                "parameters": {"instances": 2}
            },
            "backup": {
                "name": "daily_backup_trigger",
                "trigger_type": "time",
                "condition": "02:00 UTC daily",
                "action": "create_backup",
                "parameters": {"retention": "30days"}
            },
            "error_threshold": {
                "name": "error_rate_trigger",
                "trigger_type": "condition",
                "condition": "error_rate > 5%",
                "action": "alert_team",
                "parameters": {"severity": "high"}
            },
            "performance": {
                "name": "performance_trigger",
                "trigger_type": "condition",
                "condition": "response_time > 1000ms",
                "action": "scale_resources",
                "parameters": {"resource": "cpu", "amount": "25%"}
            }
        }

    def upload_document(
        self,
        name: str,
        file_type: str,
        content: str,
        document_type: Optional[str] = None
    ) -> DocumentMetadata:
        """
        Upload and process a document

        Args:
            name: Document name
            file_type: File type (pdf, docx, txt, md, json)
            content: Document content
            document_type: Optional document type (auto-detected if not provided)

        Returns:
            DocumentMetadata object
        """
        self.document_count += 1
        document_id = f"doc_{self.document_count}"

        # Auto-detect document type if not provided
        if not document_type:
            document_type = self._detect_document_type(name, content)

        # Calculate checksum (simplified)
        checksum = f"hash_{hash(content)}"

        metadata = DocumentMetadata(
            document_id=document_id,
            name=name,
            file_type=file_type,
            size=len(content),
            uploaded_at=datetime.now(timezone.utc).isoformat(),
            document_type=DocumentType(document_type),
            status=DocumentStatus.PROCESSING,
            checksum=checksum
        )

        self.documents[document_id] = metadata

        # Process document content
        self._process_document(document_id, content)

        # Update status
        metadata.status = DocumentStatus.PROCESSED

        return metadata

    def _detect_document_type(self, name: str, content: str) -> str:
        """Auto-detect document type from name and content"""
        name_lower = name.lower()
        content_lower = content.lower()

        # Check for keywords
        if any(keyword in name_lower or keyword in content_lower for keyword in
               ["requirement", "requirements", "spec"]):
            return "requirements"
        elif any(keyword in name_lower or keyword in content_lower for keyword in
                 ["design", "architecture", "technical design"]):
            return "design"
        elif any(keyword in name_lower or keyword in content_lower for keyword in
                 ["equipment", "hardware", "software list"]):
            return "equipment_list"
        elif "specification" in name_lower or "spec" in name_lower:
            return "specification"
        else:
            return "technical"

    def _process_document(self, document_id: str, content: str):
        """Process document content to extract requirements, equipment, triggers"""
        # Extract requirements
        requirements = self._extract_requirements(document_id, content)
        for req in requirements:
            self.requirements[req.requirement_id] = req

        # Extract equipment specifications
        equipment_specs = self._extract_equipment_specs(document_id, content)
        for spec in equipment_specs:
            # Select equipment based on spec
            selections = self._select_equipment(spec)
            for selection in selections:
                self.equipment[selection.equipment_id] = selection

        # Extract triggers
        document_triggers = self._extract_triggers(document_id, content)
        for trigger in document_triggers:
            self.triggers[trigger.trigger_id] = trigger

    def _extract_requirements(
        self,
        document_id: str,
        content: str
    ) -> List[DesignRequirement]:
        """Extract design requirements from document content"""
        requirements = []

        # Split into sentences/lines
        lines = content.split('\n')

        # Requirement patterns
        requirement_patterns = [
            r'the system\s+(shall|must|should)\s+(.+)',
            r'(requirement|specification):\s+(.+)',
            r'functionality:\s+(.+)',
            r'constraint:\s+(.+)'
        ]

        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            for pattern in requirement_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    self.requirement_count += 1
                    requirement_id = f"req_{self.requirement_count}"

                    # Determine category and priority
                    category = "functional"
                    priority = "medium"

                    if "constraint" in pattern.lower() or "must" in line.lower():
                        category = "constraint"
                        priority = "high"
                    elif "shall" in line.lower():
                        category = "functional"
                        priority = "high"
                    elif "should" in line.lower():
                        category = "non_functional"
                        priority = "medium"
                    elif "requirement" in line.lower():
                        category = "functional"
                        priority = "high"

                    requirement = DesignRequirement(
                        requirement_id=requirement_id,
                        text=match.group(2) if match.groups() else line,
                        category=category,
                        priority=priority,
                        source=f"{document_id}:line_{i+1}"
                    )

                    requirements.append(requirement)
                    break

        return requirements

    def _extract_equipment_specs(
        self,
        document_id: str,
        content: str
    ) -> List[Dict[str, Any]]:
        """Extract equipment specifications from document"""
        specs = []

        # Look for equipment-related sections
        equipment_keywords = ["equipment", "hardware", "software", "technology stack", "infrastructure"]
        lines = content.split('\n')

        in_equipment_section = False
        current_spec = {}

        for line in lines:
            line_lower = line.lower().strip()

            if any(keyword in line_lower for keyword in equipment_keywords):
                in_equipment_section = True
                continue

            if in_equipment_section and line:
                # Extract spec details
                if "cpu" in line_lower or "processor" in line_lower:
                    current_spec["cpu"] = line
                elif "ram" in line_lower or "memory" in line_lower:
                    current_spec["ram"] = line
                elif "storage" in line_lower or "disk" in line_lower:
                    current_spec["storage"] = line
                elif "database" in line_lower:
                    current_spec["database"] = line
                elif "framework" in line_lower:
                    current_spec["framework"] = line

                if current_spec and len(current_spec) >= 2:
                    specs.append({
                        "document_id": document_id,
                        "specs": current_spec.copy()
                    })
                    current_spec = {}

            if in_equipment_section and not line:
                in_equipment_section = False

        return specs

    def _select_equipment(
        self,
        spec: Dict[str, Any]
    ) -> List[EquipmentSelection]:
        """Select equipment based on specifications"""
        selections = []
        spec_details = spec.get("specs", {})

        # Select servers based on CPU/RAM requirements
        if "cpu" in spec_details or "ram" in spec_details:
            cpu_req = 2  # Default
            ram_req = "8GB"  # Default

            # Parse requirements (simplified)
            if "cpu" in spec_details:
                cpu_match = re.search(r'(\d+)\s*cpu', spec_details["cpu"].lower())
                if cpu_match:
                    cpu_req = int(cpu_match.group(1))

            if "ram" in spec_details:
                ram_match = re.search(r'(\d+)\s*gb', spec_details["ram"].lower())
                if ram_match:
                    ram_req = f"{ram_match.group(1)}GB"

            # Find matching server
            for server in self.equipment_catalog["hardware"]["servers"]:
                if server["specifications"]["cpu"] >= cpu_req:
                    self.equipment_count += 1
                    selection = EquipmentSelection(
                        equipment_id=f"eq_{self.equipment_count}",
                        name=server["name"],
                        type="hardware",
                        specifications=server["specifications"],
                        quantity=1,
                        cost=server["cost_per_hour"] * 730,  # Monthly cost
                        justification=f"Meets CPU ({cpu_req}) and RAM ({ram_req}) requirements"
                    )
                    selections.append(selection)
                    break

        # Select database if specified
        if "database" in spec_details:
            db_spec = spec_details["database"].lower()

            for db in self.equipment_catalog["hardware"]["databases"]:
                if db["name"].lower() in db_spec or "postgresql" in db_spec and "postgres" in db_spec:
                    self.equipment_count += 1
                    selection = EquipmentSelection(
                        equipment_id=f"eq_{self.equipment_count}",
                        name=db["name"],
                        type="hardware",
                        specifications=db["specifications"],
                        quantity=1,
                        cost=db["cost_per_hour"] * 730,
                        justification="Matches database specification"
                    )
                    selections.append(selection)
                    break

        # Select framework if specified
        if "framework" in spec_details:
            framework_spec = spec_details["framework"].lower()

            for framework in self.equipment_catalog["software"]["frameworks"]:
                if framework["name"].lower() in framework_spec:
                    self.equipment_count += 1
                    selection = EquipmentSelection(
                        equipment_id=f"eq_{self.equipment_count}",
                        name=framework["name"],
                        type="software",
                        specifications=framework["specifications"],
                        quantity=1,
                        cost=framework["cost"],
                        justification="Matches framework specification"
                    )
                    selections.append(selection)
                    break

        return selections

    def _extract_triggers(
        self,
        document_id: str,
        content: str
    ) -> List[SystemTrigger]:
        """Extract system triggers from document"""
        triggers = []

        # Look for trigger patterns
        trigger_patterns = [
            r'when\s+(.+),?\s+(should|must|will)\s+(.+)',
            r'if\s+(.+),?\s+(then|should|must)\s+(.+)',
            r'trigger:\s+(.+)',
            r'auto\s*(scale|backup|deploy)\s*when\s*(.+)'
        ]

        lines = content.split('\n')

        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            for pattern in trigger_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    self.trigger_count += 1
                    trigger_id = f"trigger_{self.trigger_count}"

                    # Extract condition and action
                    if "trigger:" in line.lower():
                        parts = line.split("trigger:", 1)[1].strip().split("->")
                        if len(parts) == 2:
                            condition = parts[0].strip()
                            action = parts[1].strip()
                        else:
                            condition = parts[0].strip()
                            action = "log_event"
                    elif "when" in line.lower():
                        condition = match.group(1)
                        action = match.group(3)
                    elif "if" in line.lower():
                        condition = match.group(1)
                        action = match.group(3)
                    else:
                        condition = match.group(2)
                        action = match.group(1)

                    # Determine trigger type
                    trigger_type = "condition"
                    if "time" in condition.lower() or "schedule" in condition.lower():
                        trigger_type = "time"
                    elif "deploy" in action.lower() or "build" in condition.lower():
                        trigger_type = "event"

                    trigger = SystemTrigger(
                        trigger_id=trigger_id,
                        name=f"Trigger from {document_id}",
                        trigger_type=trigger_type,
                        condition=condition,
                        action=action,
                        parameters={},
                        priority=5,
                        created_from=document_id
                    )

                    triggers.append(trigger)
                    break

        return triggers

    def get_document_summary(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of processed document"""
        if document_id not in self.documents:
            return None

        metadata = self.documents[document_id]

        # Count related items
        requirements = [r for r in self.requirements.values()
                       if document_id in r.source]
        equipment = [e for e in self.equipment.values()
                    if document_id in getattr(e, 'justification', '')]
        triggers = [t for t in self.triggers.values()
                   if t.created_from == document_id]

        return {
            "metadata": metadata.to_dict(),
            "requirements_extracted": len(requirements),
            "equipment_selected": len(equipment),
            "triggers_generated": len(triggers),
            "requirements": [r.to_dict() for r in requirements],
            "equipment": [e.to_dict() for e in equipment],
            "triggers": [t.to_dict() for t in triggers]
        }

    def generate_requirements_report(self) -> Dict[str, Any]:
        """Generate comprehensive requirements report"""

    def process_document(self, content: str, name: str = "unnamed", file_type: str = "text") -> Dict[str, Any]:
        """Convenience method: process a document from raw content string"""
        metadata = self.upload_document(name=name, file_type=file_type, content=content)
        return self.get_document_summary(metadata.document_id) or {"document_id": metadata.document_id}

    def analyze_document(self, content: str, name: str = "analysis", file_type: str = "text") -> Dict[str, Any]:
        """Convenience method: analyze a document and return summary"""
        return self.process_document(content, name=name, file_type=file_type)

    def extract_requirements(self, content: str) -> list:
        """Convenience method: extract requirements from raw content"""
        metadata = self.upload_document(name="requirements_extraction", file_type="text", content=content)
        reqs = [r.to_dict() for r in self.requirements.values()
                if metadata.document_id in r.source]
        return reqs

    def _count_equipment_by_type(self) -> Dict[str, int]:
        """Count equipment by type"""
        counts = {}
        for eq in self.equipment.values():
            eq_type = eq.type
            counts[eq_type] = counts.get(eq_type, 0) + 1
        return counts


if __name__ == "__main__":
    # Test document processor
    processor = DocumentProcessor()

    # Test 1: Upload requirements document
    logger.info("=== Test 1: Upload Requirements Document ===")
    requirements_doc = """
# System Requirements Document

## Functional Requirements
The system shall allow users to create accounts.
The system must support user authentication.
The system should provide real-time notifications.

## Non-Functional Requirements
Constraint: Response time must be under 200ms.
Specification: System must handle 1000 concurrent users.
Requirement: 99.9% uptime required.
    """

    metadata = processor.upload_document(
        name="requirements.txt",
        file_type="txt",
        content=requirements_doc,
        document_type="requirements"
    )
    logger.info(f"Uploaded: {metadata.name}")
    logger.info(f"Type: {metadata.document_type.value}")
    logger.info(f"Status: {metadata.status.value}")

    # Test 2: Upload design document
    logger.info("\n=== Test 2: Upload Design Document ===")
    design_doc = """
# System Design Document

## Infrastructure
Hardware: 4 CPU cores, 16GB RAM
Database: PostgreSQL
Framework: React frontend, Node.js backend

## Triggers
When deployment completes -> Deploy to staging
If CPU usage > 80% -> Scale up servers
    """

    metadata = processor.upload_document(
        name="design.txt",
        file_type="txt",
        content=design_doc,
        document_type="design"
    )
    logger.info(f"Uploaded: {metadata.name}")

    # Test 3: Get document summaries
    logger.info("\n=== Test 3: Document Summaries ===")
    for doc_id in processor.documents:
        summary = processor.get_document_summary(doc_id)
        logger.info(f"\nDocument: {summary['metadata']['name']}")
        logger.info(f"  Requirements: {summary['requirements_extracted']}")
        logger.info(f"  Equipment: {summary['equipment_selected']}")
        logger.info(f"  Triggers: {summary['triggers_generated']}")

    # Test 4: Generate report
    logger.info("\n=== Test 4: Requirements Report ===")
    report = processor.generate_requirements_report()
    logger.info(f"Total Documents: {report['total_documents']}")
    logger.info(f"Total Requirements: {report['total_requirements']}")
    logger.info(f"By Category: {report['by_category']}")
    logger.info(f"By Priority: {report['by_priority']}")
    logger.info(f"Total Equipment: {report['total_equipment']}")
    logger.info(f"Total Cost: ${report['total_equipment_cost']:.2f}/month")
    logger.info(f"Total Triggers: {report['total_triggers']}")

    # Test 5: Show extracted requirements
    logger.info("\n=== Test 5: Extracted Requirements ===")
    for req_id, req in processor.requirements.items():
        logger.info(f"\n{req_id}: {req.text}")
        logger.info(f"  Category: {req.category}, Priority: {req.priority}")

    # Test 6: Show selected equipment
    logger.info("\n=== Test 6: Selected Equipment ===")
    for eq_id, eq in processor.equipment.items():
        logger.info(f"\n{eq_id}: {eq.name}")
        logger.info(f"  Type: {eq.type}, Cost: ${eq.cost:.2f}")
        logger.info(f"  Justification: {eq.justification}")

    # Test 7: Show generated triggers
    logger.info("\n=== Test 7: Generated Triggers ===")
    for trigger_id, trigger in processor.triggers.items():
        logger.info(f"\n{trigger_id}: {trigger.name}")
        logger.info(f"  Type: {trigger.trigger_type}")
        logger.info(f"  Condition: {trigger.condition}")
        logger.info(f"  Action: {trigger.action}")
