"""
Industry Automation Wizard Module

Comprehensive wizard covering 10 industries with automation type catalog,
question-driven flow, and onboarding context integration.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Any
from enum import Enum
from datetime import datetime
import uuid

# Import for BAS/manufacturing integration
try:
    from bas_equipment_ingestion import EquipmentDataIngestion, EquipmentSpec
except ImportError:
    EquipmentDataIngestion = None
    EquipmentSpec = None


class IndustryType(Enum):
    """Industry types"""
    TECHNOLOGY = "Technology"
    HEALTHCARE = "Healthcare"
    FINANCE = "Finance"
    RETAIL = "Retail"
    MANUFACTURING = "Manufacturing"
    EDUCATION = "Education"
    PROFESSIONAL_SERVICES = "Professional Services"
    MEDIA = "Media"
    NONPROFIT = "Nonprofit"
    OTHER = "Other"


@dataclass
class AutomationType:
    """Automation type definition"""
    type_id: str
    industry: IndustryType
    name: str
    description: str
    typical_duration: str
    complexity: str  # "low", "medium", "high"
    questions: List[str]  # question_ids
    workflow_steps: List[dict]
    recommendations: List[str]
    tags: List[str]


@dataclass
class IndustryWizardQuestion:
    """Question in the wizard"""
    question_id: str
    question: str
    category: str
    required: bool
    options: List[str]
    help_text: str
    order: int
    industry_types: Set[str] = field(default_factory=set)  # empty = universal
    automation_types: Set[str] = field(default_factory=set)  # empty = universal
    recommendation: str = ""  # inline best-practice
    onboarding_key: str = ""  # pre-fill from onboarding context


@dataclass
class IndustryAutomationSpec:
    """Output specification"""
    spec_id: str
    session_id: str
    industry: str
    automation_type: str
    title: str
    description: str
    workflow_steps: List[dict]
    recommendations: List[str]
    answers: dict
    onboarding_context_used: dict
    equipment_specs: List[dict] = field(default_factory=list)
    virtual_controller_ids: List[str] = field(default_factory=list)
    estimated_setup_time: str = ""
    complexity: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "spec_id": self.spec_id,
            "session_id": self.session_id,
            "industry": self.industry,
            "automation_type": self.automation_type,
            "title": self.title,
            "description": self.description,
            "workflow_steps": self.workflow_steps,
            "recommendations": self.recommendations,
            "answers": self.answers,
            "onboarding_context_used": self.onboarding_context_used,
            "equipment_specs": self.equipment_specs,
            "virtual_controller_ids": self.virtual_controller_ids,
            "estimated_setup_time": self.estimated_setup_time,
            "complexity": self.complexity,
            "tags": self.tags,
            "created_at": self.created_at
        }


@dataclass
class IndustryAutomationSession:
    """Wizard session"""
    session_id: str
    industry: str
    automation_type: str
    questions_answered: Dict[str, dict]
    onboarding_context: dict
    pre_filled: Dict[str, str]
    status: str  # "in_progress", "completed"
    spec: Optional[IndustryAutomationSpec] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())





# ============================================================================
# AUTOMATION CATALOG - All automation types per industry  
# ============================================================================

def _build_automation_catalog() -> Dict:
    """Build complete automation catalog for all 10 industries"""
    from typing import Dict as DictType
    catalog: DictType[IndustryType, list] = {}
    
    # Helper to create automation type
    def at(type_id, name, desc, duration, complexity, recs):
        return AutomationType(
            type_id=type_id,
            industry=IndustryType.TECHNOLOGY,  # Will be set per industry
            name=name,
            description=desc,
            typical_duration=duration,
            complexity=complexity,
            questions=["goal", "stakeholders", "timeline"],
            workflow_steps=[{"step": "Setup"}, {"step": "Configure"}, {"step": "Test"}],
            recommendations=recs,
            tags=[type_id]
        )
    
    # TECHNOLOGY
    catalog[IndustryType.TECHNOLOGY] = [
        at("ci_cd_pipeline", "CI/CD Pipeline", "Continuous integration", "2-3 hours", "medium", 
           ["Use trunk-based development", "Automate rollback"]),
        at("code_review_automation", "Code Review", "Automated code review", "1-2 hours", "low",
           ["Enable automatic formatting", "Require 2+ approvals"]),
        at("deployment_monitoring", "Deployment Monitoring", "Monitor deployments", "2 hours", "medium",
           ["Monitor error rates", "Track frequency"]),
        at("bug_triage", "Bug Triage", "Auto-triage bugs", "1 hour", "low",
           ["Use severity labels", "Auto-assign by component"]),
        at("api_monitoring", "API Monitoring", "Monitor API health", "1-2 hours", "low",
           ["Monitor p99 latency", "Track error rates"]),
        at("saas_customer_onboarding", "SaaS Onboarding", "Automate customer setup", "3 hours", "high",
           ["Personalize onboarding", "Track completion"]),
        at("saas_billing_automation", "SaaS Billing", "Automate billing", "4 hours", "high",
           ["Support multiple payment methods", "Enable auto-renewal"]),
        at("security_scanning", "Security Scanning", "Vulnerability scanning", "2 hours", "medium",
           ["Scan on every PR", "Block high-severity"]),
        at("dependency_management", "Dependency Management", "Manage dependencies", "1 hour", "low",
           ["Auto-merge security patches", "Test before merging"]),
        at("user_analytics", "User Analytics", "Track user behavior", "2 hours", "medium",
           ["Respect privacy", "Track key metrics"]),
    ]
    
    # HEALTHCARE 
    catalog[IndustryType.HEALTHCARE] = [
        at("patient_intake", "Patient Intake", "Automate patient registration", "2-3 hours", "medium",
           ["HIPAA requires minimum necessary information", "Enable audit logging"]),
        at("appointment_scheduling", "Appointment Scheduling", "Automated booking", "2 hours", "low",
           ["Send 24-hour reminders", "Allow online rescheduling"]),
        at("hipaa_compliance_reporting", "HIPAA Compliance", "Generate compliance reports", "3 hours", "high",
           ["Log all PHI access", "Encrypt data"]),
        at("lab_results_routing", "Lab Results Routing", "Route lab results", "2 hours", "medium",
           ["Flag critical results", "Track provider acknowledgment"]),
        at("claims_processing", "Claims Processing", "Automate insurance claims", "4 hours", "high",
           ["Validate ICD-10 codes", "Track denial rates"]),
        at("ehr_integration", "EHR Integration", "Integrate with EHR", "5 hours", "high",
           ["Use HL7 FHIR standard", "Implement patient matching"]),
    ]
    
    # FINANCE
    catalog[IndustryType.FINANCE] = [
        at("transaction_monitoring", "Transaction Monitoring", "Monitor transactions", "3 hours", "medium",
           ["Use ML for fraud detection", "Track false positive rate"]),
        at("fraud_detection", "Fraud Detection", "Detect and prevent fraud", "4 hours", "high",
           ["Implement MFA", "Monitor for account takeover"]),
        at("regulatory_compliance_reporting", "Compliance Reporting", "Generate compliance reports", "5 hours", "high",
           ["Automate SOX compliance", "Track audit trail"]),
        at("invoice_processing", "Invoice Processing", "Automate invoice processing", "2 hours", "low",
           ["Use OCR for data extraction", "Implement 3-way matching"]),
        at("portfolio_rebalancing", "Portfolio Rebalancing", "Automate rebalancing", "3 hours", "medium",
           ["Consider tax implications", "Use threshold bands"]),
        at("kyc_automation", "KYC Automation", "Automate KYC checks", "3 hours", "medium",
           ["Use government ID verification", "Monitor for changes"]),
    ]
    
    # RETAIL
    catalog[IndustryType.RETAIL] = [
        at("inventory_management", "Inventory Management", "Automate inventory tracking", "3 hours", "medium",
           ["Use barcode scanning", "Implement just-in-time ordering"]),
        at("order_fulfillment", "Order Fulfillment", "Automate order processing", "2 hours", "low",
           ["Optimize picking routes", "Provide tracking updates"]),
        at("customer_loyalty_program", "Loyalty Program", "Manage loyalty points", "3 hours", "medium",
           ["Personalize rewards", "Send expiration reminders"]),
        at("returns_processing", "Returns Processing", "Automate returns", "2 hours", "low",
           ["Offer free returns", "Track return rates"]),
        at("demand_forecasting", "Demand Forecasting", "Forecast product demand", "4 hours", "high",
           ["Use ML models", "Factor in promotions"]),
        at("dynamic_pricing", "Dynamic Pricing", "Automate price adjustments", "3 hours", "high",
           ["Consider demand elasticity", "Track conversion rates"]),
    ]
    
    # MANUFACTURING (includes BAS types)
    catalog[IndustryType.MANUFACTURING] = [
        at("quality_control_inspection", "Quality Control", "Automate inspections", "3 hours", "medium",
           ["Use vision systems", "Track defect rates"]),
        at("supply_chain_management", "Supply Chain", "Optimize supply chain", "4 hours", "high",
           ["Implement just-in-time", "Use RFID tracking"]),
        at("predictive_maintenance", "Predictive Maintenance", "Predict equipment failures", "4 hours", "high",
           ["Use vibration analysis", "Track MTBF metrics"]),
        at("production_scheduling", "Production Scheduling", "Optimize schedules", "3 hours", "medium",
           ["Balance line utilization", "Minimize changeovers"]),
        at("bas_energy_management", "BAS Energy Management", "Building automation", "5-6 hours", "high",
           ["ASHRAE 90.1 compliance required", "Monitor energy consumption"]),
        at("bas_hvac_control", "BAS HVAC Control", "HVAC control automation", "4 hours", "high",
           ["ASHRAE 62.1 minimum OA requirement", "Enable demand-controlled ventilation"]),
        at("industrial_plc_integration", "Industrial PLC Integration", "Integrate PLCs", "4 hours", "high",
           ["Implement redundant safety interlocks", "Log all alarm events"]),
        at("oee_tracking", "OEE Tracking", "Track Overall Equipment Effectiveness", "3 hours", "medium",
           ["Target 85% OEE", "Track Six Big Losses"]),
    ]
    
    # EDUCATION
    catalog[IndustryType.EDUCATION] = [
        at("student_enrollment", "Student Enrollment", "Automate student enrollment", "3 hours", "medium",
           ["Offer online enrollment", "Send confirmation emails"]),
        at("grade_automation", "Grade Automation", "Automate grading", "2 hours", "low",
           ["Use rubrics", "Provide feedback"]),
        at("course_scheduling", "Course Scheduling", "Optimize course schedules", "3 hours", "medium",
           ["Balance instructor load", "Minimize student conflicts"]),
        at("learning_analytics", "Learning Analytics", "Analyze student learning data", "3 hours", "medium",
           ["Track engagement", "Identify at-risk students"]),
        at("attendance_tracking", "Attendance Tracking", "Track student attendance", "1 hour", "low",
           ["Use QR codes", "Notify parents"]),
        at("parent_communications", "Parent Communications", "Automate parent communications", "2 hours", "low",
           ["Use multi-channel approach", "Translate for non-English speakers"]),
    ]
    
    # PROFESSIONAL_SERVICES
    catalog[IndustryType.PROFESSIONAL_SERVICES] = [
        at("project_management_automation", "Project Management", "Automate project workflows", "3 hours", "medium",
           ["Use agile methodology", "Track burn rate"]),
        at("client_reporting", "Client Reporting", "Generate client reports", "2 hours", "low",
           ["Automate monthly reports", "Use dashboards"]),
        at("billable_hours_tracking", "Billable Hours Tracking", "Track billable time", "2 hours", "low",
           ["Track utilization rates", "Set hourly targets"]),
        at("proposal_generation", "Proposal Generation", "Generate proposals", "2 hours", "medium",
           ["Use standard templates", "Track win rates"]),
        at("contract_lifecycle_management", "Contract Lifecycle", "Manage contract lifecycle", "3 hours", "high",
           ["Alert on expiration", "Track obligations"]),
        at("resource_allocation", "Resource Allocation", "Optimize resource allocation", "3 hours", "medium",
           ["Balance workload", "Track availability"]),
    ]
    
    # MEDIA
    catalog[IndustryType.MEDIA] = [
        at("content_publishing_workflow", "Content Publishing", "Automate content publishing", "2 hours", "medium",
           ["Use editorial calendar", "Schedule posts"]),
        at("social_media_scheduling", "Social Media Scheduling", "Schedule social media posts", "1 hour", "low",
           ["Post at optimal times", "Use hashtags"]),
        at("audience_analytics", "Audience Analytics", "Analyze audience engagement", "2 hours", "medium",
           ["Track engagement rates", "Segment audiences"]),
        at("rights_management", "Rights Management", "Manage content rights", "3 hours", "high",
           ["Track usage rights", "Automate renewals"]),
        at("subscriber_lifecycle", "Subscriber Lifecycle", "Manage subscriber journey", "3 hours", "medium",
           ["Personalize content", "Reduce churn"]),
        at("content_moderation", "Content Moderation", "Moderate user-generated content", "2 hours", "medium",
           ["Use AI for initial screening", "Human review for edge cases"]),
    ]
    
    # NONPROFIT
    catalog[IndustryType.NONPROFIT] = [
        at("donor_management", "Donor Management", "Manage donor relationships", "3 hours", "medium",
           ["Acknowledge donations within 48 hours", "Track lifetime value"]),
        at("grant_lifecycle_tracking", "Grant Lifecycle", "Track grant applications", "4 hours", "high",
           ["Maintain grant calendar", "Track compliance"]),
        at("volunteer_coordination", "Volunteer Coordination", "Coordinate volunteer activities", "2 hours", "low",
           ["Use volunteer portal", "Recognize contributions"]),
        at("impact_reporting", "Impact Reporting", "Generate impact reports", "3 hours", "medium",
           ["Use Theory of Change", "Share stories"]),
        at("fundraising_automation", "Fundraising Automation", "Automate fundraising campaigns", "3 hours", "medium",
           ["Use peer-to-peer fundraising", "Send thank you emails"]),
        at("beneficiary_tracking", "Beneficiary Tracking", "Track program beneficiaries", "3 hours", "medium",
           ["Protect privacy", "Track outcomes"]),
    ]
    
    # OTHER (generic)
    catalog[IndustryType.OTHER] = [
        at("task_automation", "Task Automation", "Automate repetitive tasks", "1-2 hours", "low",
           ["Start with high-volume tasks", "Test thoroughly"]),
        at("data_processing_pipeline", "Data Processing Pipeline", "Automated data processing", "3 hours", "medium",
           ["Validate data quality", "Handle errors gracefully"]),
        at("notification_workflow", "Notification Workflow", "Automate notifications", "1 hour", "low",
           ["Avoid notification fatigue", "Allow opt-out"]),
        at("reporting_automation", "Reporting Automation", "Automate report generation", "2 hours", "low",
           ["Use templates", "Automate scheduling"]),
        at("system_integration_sync", "System Integration Sync", "Sync data between systems", "3 hours", "medium",
           ["Handle conflicts gracefully", "Log all sync operations"]),
        at("approval_workflow", "Approval Workflow", "Automate approval processes", "2 hours", "low",
           ["Set SLAs for approvals", "Allow delegation"]),
    ]
    
    # Set correct industry on each automation type
    for industry, automations in catalog.items():
        for automation in automations:
            automation.industry = industry
    
    return catalog


AUTOMATION_CATALOG = _build_automation_catalog()


# ============================================================================
# QUESTION BANK - Questions for the wizard
# ============================================================================

def _build_question_bank() -> List[IndustryWizardQuestion]:
    """Build the question bank"""
    questions = []
    
    # Universal questions
    questions.append(IndustryWizardQuestion(
        question_id="industry_selection",
        question="Which industry best describes your organization?",
        category="industry",
        required=True,
        options=[ind.value for ind in IndustryType],
        help_text="Select the industry that best matches your organization",
        order=1,
        recommendation="Selecting the correct industry ensures you see relevant automation types and best practices."
    ))
    
    questions.append(IndustryWizardQuestion(
        question_id="automation_type_selection",
        question="What type of automation do you want to set up?",
        category="automation_type",
        required=True,
        options=[],  # Dynamically populated
        help_text="Choose the automation type that matches your needs",
        order=2,
        recommendation="Choose automations that address your highest-impact pain points first."
    ))
    
    questions.append(IndustryWizardQuestion(
        question_id="goal",
        question="What is the primary goal of this automation?",
        category="goal",
        required=True,
        options=["Reduce manual work", "Improve accuracy", "Increase speed", "Ensure compliance", "Enhance visibility"],
        help_text="Define the main objective",
        order=3,
        recommendation="Clear goals enable better measurement of automation success. Set specific, measurable targets."
    ))
    
    questions.append(IndustryWizardQuestion(
        question_id="stakeholders",
        question="Who will be the primary users of this automation?",
        category="stakeholders",
        required=True,
        options=["Individual contributors", "Team leads", "Managers", "Executives", "External users"],
        help_text="Identify primary user groups",
        order=4,
        recommendation="Involve stakeholders early in design. Successful automation requires user buy-in and training.",
        onboarding_key="team_size"
    ))
    
    questions.append(IndustryWizardQuestion(
        question_id="timeline",
        question="What is your target timeline?",
        category="timeline",
        required=True,
        options=["Immediate (1-2 weeks)", "Short-term (1 month)", "Medium-term (3 months)", "Long-term (6+ months)"],
        help_text="When do you need this automation live?",
        order=5,
        recommendation="Start with pilot phase in production. Iterate based on real-world usage before full rollout."
    ))
    
    # Technology-specific questions
    questions.append(IndustryWizardQuestion(
        question_id="repo_url",
        question="What is your repository URL?",
        category="technical",
        required=False,
        options=[],
        help_text="GitHub/GitLab repository URL",
        order=10,
        industry_types={"Technology"},
        automation_types={"ci_cd_pipeline", "code_review_automation"},
        recommendation="Use trunk-based development with feature flags rather than long-lived branches. Automate rollback on >1% error rate spike."
    ))
    
    questions.append(IndustryWizardQuestion(
        question_id="branch_strategy",
        question="What branching strategy do you use?",
        category="technical",
        required=False,
        options=["Trunk-based", "Git Flow", "GitHub Flow", "GitLab Flow"],
        help_text="Your Git branching strategy",
        order=11,
        industry_types={"Technology"},
        automation_types={"ci_cd_pipeline"},
        recommendation="Trunk-based development with feature flags enables faster feedback and reduces merge conflicts."
    ))
    
    # Healthcare-specific questions
    questions.append(IndustryWizardQuestion(
        question_id="hipaa_compliance",
        question="Does this require HIPAA compliance?",
        category="compliance",
        required=True,
        options=["Yes", "No"],
        help_text="HIPAA applies to Protected Health Information (PHI)",
        order=10,
        industry_types={"Healthcare"},
        recommendation="HIPAA requires minimum necessary information. Collect only fields needed for care. Enable audit logging on all PHI access."
    ))
    
    questions.append(IndustryWizardQuestion(
        question_id="patient_data_fields",
        question="What patient data fields are required?",
        category="data",
        required=False,
        options=["Name", "DOB", "MRN", "Insurance", "Contact info", "Diagnosis", "Medications"],
        help_text="Select required patient data fields",
        order=11,
        industry_types={"Healthcare"},
        automation_types={"patient_intake", "ehr_integration"},
        recommendation="Follow HIPAA minimum necessary standard. Only collect data essential for the workflow."
    ))
    
    # Manufacturing BAS-specific questions
    questions.append(IndustryWizardQuestion(
        question_id="equipment_upload",
        question="Upload equipment point list (CSV/JSON/EDE) or enter manually?",
        category="equipment",
        required=True,
        options=["Upload file", "Enter manually", "Use template"],
        help_text="Provide equipment data for BAS integration",
        order=10,
        industry_types={"Manufacturing"},
        automation_types={"bas_energy_management", "bas_hvac_control", "bas_power_monitoring"},
        recommendation="ASHRAE 90.1 Appendix G requires energy monitoring. Use EDE format for BACnet devices for best compatibility."
    ))
    
    questions.append(IndustryWizardQuestion(
        question_id="protocol_selection",
        question="What protocol does your equipment use?",
        category="technical",
        required=True,
        options=["BACnet/IP", "BACnet MS/TP", "Modbus TCP", "Modbus RTU", "OPC-UA", "OPC-DA"],
        help_text="Communication protocol for equipment",
        order=11,
        industry_types={"Manufacturing"},
        automation_types={"bas_energy_management", "bas_hvac_control", "bas_power_monitoring", "industrial_plc_integration"},
        recommendation="BACnet/IP is standard for HVAC. Modbus TCP for industrial. OPC-UA for modern PLCs with security."
    ))
    
    questions.append(IndustryWizardQuestion(
        question_id="ip_address",
        question="What is the equipment IP address?",
        category="technical",
        required=False,
        options=[],
        help_text="IP address for network-based protocols",
        order=12,
        industry_types={"Manufacturing"},
        automation_types={"bas_energy_management", "bas_hvac_control", "bas_power_monitoring"},
        recommendation="Use static IP or DHCP reservation. Document all equipment IP addresses in network diagram."
    ))
    
    questions.append(IndustryWizardQuestion(
        question_id="point_verification",
        question="Verify all points are correctly configured?",
        category="verification",
        required=True,
        options=["Yes - verify now", "Skip verification"],
        help_text="Wiring verification checks point configuration",
        order=13,
        industry_types={"Manufacturing"},
        automation_types={"bas_energy_management", "bas_hvac_control", "bas_power_monitoring"},
        recommendation="Always verify wiring before commissioning. Check that limits, units, and instance numbers are correct."
    ))
    
    # Add more industry-specific questions...
    # Finance
    questions.append(IndustryWizardQuestion(
        question_id="regulations",
        question="Which regulations apply?",
        category="compliance",
        required=True,
        options=["SOX", "GDPR", "PCI-DSS", "Dodd-Frank", "MiFID II", "Other"],
        help_text="Applicable financial regulations",
        order=10,
        industry_types={"Finance"},
        automation_types={"regulatory_compliance_reporting", "audit_trail_automation"},
        recommendation="Maintain comprehensive audit trails. SOX requires segregation of duties and change management controls."
    ))
    
    # Retail
    questions.append(IndustryWizardQuestion(
        question_id="sku_count",
        question="How many SKUs do you manage?",
        category="scale",
        required=False,
        options=["<100", "100-1000", "1000-10000", ">10000"],
        help_text="Number of unique products (SKUs)",
        order=10,
        industry_types={"Retail"},
        automation_types={"inventory_management", "demand_forecasting"},
        recommendation="High SKU counts benefit from automated reorder point calculations and demand forecasting."
    ))
    
    # Education
    questions.append(IndustryWizardQuestion(
        question_id="grading_system",
        question="What grading system do you use?",
        category="academic",
        required=False,
        options=["Letter grades (A-F)", "Percentage (0-100)", "GPA (4.0 scale)", "Standards-based"],
        help_text="Your institution''s grading system",
        order=10,
        industry_types={"Education"},
        automation_types={"grade_automation"},
        recommendation="Use rubrics for consistency. Provide timely feedback to students within 1 week of submission."
    ))
    
    # Professional Services
    questions.append(IndustryWizardQuestion(
        question_id="billing_rates",
        question="What is your billing rate structure?",
        category="billing",
        required=False,
        options=["Hourly", "Fixed fee", "Retainer", "Value-based"],
        help_text="How you bill clients",
        order=10,
        industry_types={"Professional Services"},
        automation_types={"billable_hours_tracking", "client_reporting"},
        recommendation="Target 70-75% billable utilization for professional services firms. Track realization rates."
    ))
    
    # Media
    questions.append(IndustryWizardQuestion(
        question_id="platforms",
        question="Which social media platforms?",
        category="channels",
        required=False,
        options=["Twitter", "Facebook", "LinkedIn", "Instagram", "TikTok", "YouTube"],
        help_text="Platforms for social media posting",
        order=10,
        industry_types={"Media"},
        automation_types={"social_media_scheduling"},
        recommendation="Post at platform-specific optimal times. Use native scheduling tools for best reach."
    ))
    
    # Nonprofit
    questions.append(IndustryWizardQuestion(
        question_id="donor_segments",
        question="How do you segment donors?",
        category="fundraising",
        required=False,
        options=["By donation amount", "By frequency", "By program interest", "By engagement level"],
        help_text="Donor segmentation strategy",
        order=10,
        industry_types={"Nonprofit"},
        automation_types={"donor_management", "fundraising_automation"},
        recommendation="Acknowledge all donations within 48 hours. Segment donors for targeted communications."
    ))
    
    return questions


QUESTION_BANK = _build_question_bank()


# ============================================================================
# IndustryAutomationWizard - Main wizard class
# ============================================================================

class IndustryAutomationWizard:
    """Main wizard for industry automation setup"""
    
    def __init__(self):
        self.sessions: Dict[str, IndustryAutomationSession] = {}
        self.catalog = AUTOMATION_CATALOG
        self.questions = QUESTION_BANK
    
    def create_session(
        self,
        industry: Optional[str] = None,
        automation_type: Optional[str] = None,
        onboarding_context: Optional[dict] = None
    ) -> IndustryAutomationSession:
        """Create a new wizard session"""
        session_id = str(uuid.uuid4())
        
        if onboarding_context is None:
            onboarding_context = {}
        
        # Pre-fill from onboarding context
        pre_filled = {}
        if industry:
            pre_filled["industry_selection"] = industry
        if automation_type:
            pre_filled["automation_type_selection"] = automation_type
        
        # Check onboarding context for pre-fills
        for question in self.questions:
            if question.onboarding_key and question.onboarding_key in onboarding_context:
                pre_filled[question.question_id] = str(onboarding_context[question.onboarding_key])
        
        session = IndustryAutomationSession(
            session_id=session_id,
            industry=industry or "",
            automation_type=automation_type or "",
            questions_answered={},
            onboarding_context=onboarding_context,
            pre_filled=pre_filled,
            status="in_progress"
        )
        
        self.sessions[session_id] = session
        return session
    
    def next_question(self, session_id: str) -> Optional[dict]:
        """Get the next unanswered question"""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        # Filter questions based on industry and automation type
        applicable_questions = []
        for q in sorted(self.questions, key=lambda x: x.order):
            # Check if already answered
            if q.question_id in session.questions_answered:
                continue
            
            # Check if pre-filled
            if q.question_id in session.pre_filled:
                continue
            
            # Check industry filter
            if q.industry_types and session.industry and session.industry not in q.industry_types:
                continue
            
            # Check automation type filter
            if q.automation_types and session.automation_type and session.automation_type not in q.automation_types:
                continue
            
            applicable_questions.append(q)
        
        if not applicable_questions:
            return None
        
        # Return first unanswered question
        question = applicable_questions[0]
        
        # For automation_type_selection, populate options dynamically
        options = question.options
        if question.question_id == "automation_type_selection" and session.industry:
            options = self.get_automation_types(session.industry)
        
        return {
            "question_id": question.question_id,
            "question": question.question,
            "category": question.category,
            "required": question.required,
            "options": options if isinstance(options, list) else [str(o) for o in options],
            "help_text": question.help_text,
            "recommendation": question.recommendation
        }
    
    def answer(self, session_id: str, question_id: str, answer: str) -> dict:
        """Record an answer and return progress"""
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        # Record answer
        session.questions_answered[question_id] = {
            "answer": answer,
            "timestamp": datetime.now().isoformat()
        }
        
        # Update session fields
        if question_id == "industry_selection":
            session.industry = answer
        elif question_id == "automation_type_selection":
            session.automation_type = answer
        
        # Calculate progress
        total_questions = len([q for q in self.questions 
                              if (not q.industry_types or session.industry in q.industry_types)
                              and (not q.automation_types or session.automation_type in q.automation_types)])
        answered = len(session.questions_answered) + len(session.pre_filled)
        
        return {
            "success": True,
            "progress": f"{answered}/{total_questions}",
            "percentage": int((answered / max(total_questions, 1)) * 100)
        }
    
    def get_automation_types(self, industry: str) -> List[dict]:
        """Get automation types for an industry"""
        # Find industry enum
        industry_enum = None
        for ind in IndustryType:
            if ind.value == industry or ind.name == industry:
                industry_enum = ind
                break
        
        if not industry_enum or industry_enum not in self.catalog:
            return []
        
        automation_types = self.catalog[industry_enum]
        return [{"id": at.type_id, "name": at.name, "description": at.description} 
                for at in automation_types]
    
    def generate_spec(self, session_id: str) -> Optional[IndustryAutomationSpec]:
        """Generate the final automation spec"""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        # Find automation type details
        industry_enum = None
        for ind in IndustryType:
            if ind.value == session.industry or ind.name == session.industry:
                industry_enum = ind
                break
        
        automation_detail = None
        if industry_enum and industry_enum in self.catalog:
            for at in self.catalog[industry_enum]:
                if at.type_id == session.automation_type:
                    automation_detail = at
                    break
        
        if not automation_detail:
            return None
        
        # Combine answers and pre-filled
        all_answers = {**session.pre_filled, **{k: v["answer"] for k, v in session.questions_answered.items()}}
        
        # Build spec
        title = f"{automation_detail.name} Automation"
        description = automation_detail.description
        
        # Collect recommendations
        recommendations = list(automation_detail.recommendations)
        
        # Add question-specific recommendations
        for q in self.questions:
            if q.question_id in session.questions_answered and q.recommendation:
                if q.recommendation not in recommendations:
                    recommendations.append(q.recommendation)
        
        # For BAS types, add equipment-specific recommendations
        equipment_specs = []
        virtual_controller_ids = []
        if session.automation_type in ["bas_energy_management", "bas_hvac_control", "bas_power_monitoring"]:
            if EquipmentDataIngestion:
                ingestion = EquipmentDataIngestion()
                # Simulate equipment spec (in real implementation, would parse uploaded file)
                # For now, just add recommendations
                mock_spec_dict = {"equipment_name": "Mock Equipment", "equipment_type": "AHU"}
                if hasattr(ingestion, 'get_recommendations'):
                    # Can't call get_recommendations without a real EquipmentSpec
                    # Add generic BAS recommendations
                    recommendations.append("ASHRAE 90.1 requires building energy monitoring")
                    recommendations.append("Commission all control sequences per ASHRAE Guideline 1.1")
        
        spec = IndustryAutomationSpec(
            spec_id=str(uuid.uuid4()),
            session_id=session_id,
            industry=session.industry,
            automation_type=session.automation_type,
            title=title,
            description=description,
            workflow_steps=automation_detail.workflow_steps,
            recommendations=recommendations[:10],  # Max 10
            answers=all_answers,
            onboarding_context_used=session.onboarding_context,
            equipment_specs=equipment_specs,
            virtual_controller_ids=virtual_controller_ids,
            estimated_setup_time=automation_detail.typical_duration,
            complexity=automation_detail.complexity,
            tags=automation_detail.tags
        )
        
        session.spec = spec
        session.status = "completed"
        
        return spec
    
    def get_recommendations(self, session_id: str) -> List[str]:
        """Get all accumulated recommendations so far"""
        session = self.sessions.get(session_id)
        if not session:
            return []
        
        recommendations = []
        
        # Get recommendations from answered questions
        for q in self.questions:
            if q.question_id in session.questions_answered and q.recommendation:
                if q.recommendation not in recommendations:
                    recommendations.append(q.recommendation)
        
        return recommendations
    
    def get_session(self, session_id: str) -> Optional[IndustryAutomationSession]:
        """Get session by ID"""
        return self.sessions.get(session_id)
