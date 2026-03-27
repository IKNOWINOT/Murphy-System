"""
Synthetic Interview Engine — 21-Question Technical Elicitation
==============================================================
Structured knowledge elicitation using the 21-question synthetic
interview method applied to technical systems. LLM-inference mode
derives implicit answers from every statement. Adapts output to
multiple reading levels (high-school and above).

Copyright (c) 2020 Inoni Limited Liability Company  Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReadingLevel(str, Enum):
    ELEMENTARY = "elementary"
    MIDDLE_SCHOOL = "middle_school"
    HIGH_SCHOOL = "high_school"
    TECHNICAL_COLLEGE = "technical_college"
    PROFESSIONAL = "professional"
    EXPERT = "expert"


# ---------------------------------------------------------------------------
# 21 Question IDs and bank
# ---------------------------------------------------------------------------

QUESTION_IDS = [
    "q01","q02","q03","q04","q05","q06","q07","q08","q09","q10",
    "q11","q12","q13","q14","q15","q16","q17","q18","q19","q20","q21",
]

QUESTION_BANK: Dict[str, Dict[str, str]] = {
    "q01": {
        ReadingLevel.HIGH_SCHOOL: "What does this system do? What is its main job?",
        ReadingLevel.TECHNICAL_COLLEGE: "What is the primary function and operational purpose of this system?",
        ReadingLevel.PROFESSIONAL: "Describe the primary function, operational scope, and value proposition.",
        ReadingLevel.EXPERT: "Define the functional requirements, operational envelope, and performance objectives.",
        "topic": "primary_function",
        "hint": "Listen for: equipment type, control objective, output product or service",
    },
    "q02": {
        ReadingLevel.HIGH_SCHOOL: "What does this system connect to? What goes in and what comes out?",
        ReadingLevel.TECHNICAL_COLLEGE: "What are the system inputs, outputs, and integration points?",
        ReadingLevel.PROFESSIONAL: "Describe the upstream dependencies and downstream consumers of this system.",
        ReadingLevel.EXPERT: "Detail the I/O interfaces, communication protocols, and integration architecture.",
        "topic": "connections",
        "hint": "Listen for: field devices, network protocols, upstream systems, data flows",
    },
    "q03": {
        ReadingLevel.HIGH_SCHOOL: "What can go wrong with this system? What breaks most often?",
        ReadingLevel.TECHNICAL_COLLEGE: "What are the common failure modes and their impacts?",
        ReadingLevel.PROFESSIONAL: "Describe the failure mode hierarchy: safety-critical, operational, and nuisance faults.",
        ReadingLevel.EXPERT: "Provide FMEA-level failure modes with detection methods and mitigation strategies.",
        "topic": "failure_modes",
        "hint": "Listen for: alarms, downtime, maintenance history, safety incidents",
    },
    "q04": {
        ReadingLevel.HIGH_SCHOOL: "What makes this system start or stop? What triggers it to take action?",
        ReadingLevel.TECHNICAL_COLLEGE: "What events, schedules, or sensor readings trigger system actions?",
        ReadingLevel.PROFESSIONAL: "Define the control triggers: setpoints, schedules, events, and interlocks.",
        ReadingLevel.EXPERT: "Enumerate the state-transition triggers and their precedence hierarchy.",
        "topic": "triggers",
        "hint": "Listen for: schedules, setpoints, interlocks, alarms, manual overrides",
    },
    "q05": {
        ReadingLevel.HIGH_SCHOOL: "Who uses this system? Who depends on it working correctly?",
        ReadingLevel.TECHNICAL_COLLEGE: "Who are the primary operators, maintainers, and downstream stakeholders?",
        ReadingLevel.PROFESSIONAL: "Identify all stakeholder groups and their interaction with the system.",
        ReadingLevel.EXPERT: "Map the stakeholder landscape including operators, owners, regulators, and users.",
        "topic": "stakeholders",
        "hint": "Listen for: operators, facility managers, tenants, regulators, customers",
    },
    "q06": {
        ReadingLevel.HIGH_SCHOOL: "What are the rules this system must follow? What are its limits?",
        ReadingLevel.TECHNICAL_COLLEGE: "What regulatory, code, and operational constraints govern this system?",
        ReadingLevel.PROFESSIONAL: "Define the governing codes, standards, and operational constraints.",
        ReadingLevel.EXPERT: "Enumerate applicable codes (ASHRAE, NEC, IBC), standards (ANSI, ISA), and contractual requirements.",
        "topic": "constraints",
        "hint": "Listen for: ASHRAE codes, OSHA, EPA, building codes, contractual SLAs",
    },
    "q07": {
        ReadingLevel.HIGH_SCHOOL: "How do you know this system is working well? What numbers matter most?",
        ReadingLevel.TECHNICAL_COLLEGE: "What KPIs and performance metrics measure system success?",
        ReadingLevel.PROFESSIONAL: "Define the KPI framework: leading indicators, lagging indicators, and SLA metrics.",
        ReadingLevel.EXPERT: "Specify the performance metrics with measurement methodology, targets, and acceptance criteria.",
        "topic": "kpis",
        "hint": "Listen for: efficiency targets, uptime SLAs, energy use, production rate, comfort scores",
    },
    "q08": {
        ReadingLevel.HIGH_SCHOOL: "How does this system change over time? Does it behave differently in summer vs winter?",
        ReadingLevel.TECHNICAL_COLLEGE: "How does system behaviour vary with load, season, or operating conditions?",
        ReadingLevel.PROFESSIONAL: "Describe the dynamic operating envelope and load-response behaviour.",
        ReadingLevel.EXPERT: "Characterise the control response, load-following capability, and seasonal operating modes.",
        "topic": "dynamic_behavior",
        "hint": "Listen for: seasonal changes, load profiles, part-load operation, ramp rates",
    },
    "q09": {
        ReadingLevel.HIGH_SCHOOL: "What must never happen with this system? What are the safety rules?",
        ReadingLevel.TECHNICAL_COLLEGE: "What safety interlocks, emergency procedures, and compliance requirements exist?",
        ReadingLevel.PROFESSIONAL: "Define the safety-critical constraints, interlocks, and regulatory compliance requirements.",
        ReadingLevel.EXPERT: "Enumerate SIL-rated interlocks, life-safety sequences, and compliance obligations (OSHA, EPA, ASHRAE 15).",
        "topic": "safety_compliance",
        "hint": "Listen for: OSHA, EPA, ASHRAE 15, fire codes, high-limit safeties, emergency shutoffs",
    },
    "q10": {
        ReadingLevel.HIGH_SCHOOL: "What costs the most to run? Where does most of the energy or money go?",
        ReadingLevel.TECHNICAL_COLLEGE: "What are the dominant operating costs: energy, maintenance, materials?",
        ReadingLevel.PROFESSIONAL: "Identify the cost drivers and their relative magnitude in the operating budget.",
        ReadingLevel.EXPERT: "Quantify the cost structure: energy $/kBtu, maintenance $/sqft, capital replacement cycles.",
        "topic": "resource_costs",
        "hint": "Listen for: energy bills, maintenance hours, replacement parts, utility demand charges",
    },
    "q11": {
        ReadingLevel.HIGH_SCHOOL: "What takes the most time? What slows things down?",
        ReadingLevel.TECHNICAL_COLLEGE: "What activities consume the most time in operations and maintenance?",
        ReadingLevel.PROFESSIONAL: "Identify the time-intensive processes and their contribution to downtime or cost.",
        ReadingLevel.EXPERT: "Analyse the time-cost topology: MTTR, PM frequency, commissioning duration, start-up time.",
        "topic": "time_costs",
        "hint": "Listen for: commissioning time, maintenance cycles, start-up delays, troubleshooting",
    },
    "q12": {
        ReadingLevel.HIGH_SCHOOL: "What tasks happen over and over again? What does this system do every day?",
        ReadingLevel.TECHNICAL_COLLEGE: "What repetitive tasks, control loops, or scheduled operations occur regularly?",
        ReadingLevel.PROFESSIONAL: "Describe the recurring operational sequences and their automation potential.",
        ReadingLevel.EXPERT: "Map the cyclic control sequences, scheduled tasks, and candidates for further automation.",
        "topic": "repetitive_tasks",
        "hint": "Listen for: daily start/stop, setpoint resets, filter checks, report generation",
    },
    "q13": {
        ReadingLevel.HIGH_SCHOOL: "What is hardest to understand about this system? What requires special training?",
        ReadingLevel.TECHNICAL_COLLEGE: "What domain expertise is required to operate and maintain this system?",
        ReadingLevel.PROFESSIONAL: "Identify the knowledge domains and skill gaps that create operational risk.",
        ReadingLevel.EXPERT: "Define the competency requirements: certifications, OEM training, domain expertise.",
        "topic": "expertise_required",
        "hint": "Listen for: certifications, OEM training, specialised tools, tribal knowledge",
    },
    "q14": {
        ReadingLevel.HIGH_SCHOOL: "What does this system need to work? What other things does it depend on?",
        ReadingLevel.TECHNICAL_COLLEGE: "What upstream systems, utilities, and services must be available for this system to operate?",
        ReadingLevel.PROFESSIONAL: "Map the dependency hierarchy: utilities, networks, upstream systems, and organisational dependencies.",
        ReadingLevel.EXPERT: "Document the dependency graph with single points of failure and redundancy paths.",
        "topic": "dependencies",
        "hint": "Listen for: electrical power, chilled water, network connectivity, compressed air, other systems",
    },
    "q15": {
        ReadingLevel.HIGH_SCHOOL: "If you could fix one thing right now, what would it be? What frustrates people most?",
        ReadingLevel.TECHNICAL_COLLEGE: "What are the top pain points that limit system performance or reliability?",
        ReadingLevel.PROFESSIONAL: "Identify the performance gaps and improvement opportunities with highest impact.",
        ReadingLevel.EXPERT: "Prioritise the technical debt, performance gaps, and improvement opportunities by ROI.",
        "topic": "pain_points",
        "hint": "Listen for: alarm floods, manual workarounds, inefficiencies, reliability issues",
    },
    "q16": {
        ReadingLevel.HIGH_SCHOOL: "What important things about this system are not obvious? What do people miss?",
        ReadingLevel.TECHNICAL_COLLEGE: "What latent factors or hidden dependencies affect system performance?",
        ReadingLevel.PROFESSIONAL: "Identify the non-obvious factors: second-order effects, latent degradation, hidden costs.",
        ReadingLevel.EXPERT: "Characterise the latent failure mechanisms, hidden performance factors, and second-order effects.",
        "topic": "latent_factors",
        "hint": "Listen for: humidity effects, thermal mass, occupant behaviour, network latency",
    },
    "q17": {
        ReadingLevel.HIGH_SCHOOL: "What surprised you when you first learned about this system? What did you not expect?",
        ReadingLevel.TECHNICAL_COLLEGE: "What counterintuitive behaviours or unexpected interactions did you discover?",
        ReadingLevel.PROFESSIONAL: "Describe the counterintuitive findings that changed your understanding of this system.",
        ReadingLevel.EXPERT: "Identify the emergent behaviours and non-linear interactions that are not obvious from first principles.",
        "topic": "surprises",
        "hint": "Listen for: unexpected interactions, counterintuitive setpoints, surprising failure causes",
    },
    "q18": {
        ReadingLevel.HIGH_SCHOOL: "How does this system compare to others like it? Is this the best way to do it?",
        ReadingLevel.TECHNICAL_COLLEGE: "How does this system compare to industry benchmarks and alternative approaches?",
        ReadingLevel.PROFESSIONAL: "Benchmark this system against best-in-class alternatives and industry standards.",
        ReadingLevel.EXPERT: "Perform a comparative analysis: performance benchmarks, technology alternatives, and strategic fit.",
        "topic": "comparisons",
        "hint": "Listen for: competing technologies, industry benchmarks, best practices, upgrade paths",
    },
    "q19": {
        ReadingLevel.HIGH_SCHOOL: "How did this system get to be the way it is? What changed over time?",
        ReadingLevel.TECHNICAL_COLLEGE: "What is the history of this system and how has it evolved?",
        ReadingLevel.PROFESSIONAL: "Describe the system evolution: design intent vs actual deployment, changes over time.",
        ReadingLevel.EXPERT: "Document the system history including design basis, modifications, and accumulated technical debt.",
        "topic": "history",
        "hint": "Listen for: original design intent, modifications, additions, obsolete components",
    },
    "q20": {
        ReadingLevel.HIGH_SCHOOL: "Are there special situations where the normal rules do not apply? Any edge cases?",
        ReadingLevel.TECHNICAL_COLLEGE: "What exception conditions, edge cases, or unusual operating modes exist?",
        ReadingLevel.PROFESSIONAL: "Enumerate the exception scenarios and edge cases that require special handling.",
        ReadingLevel.EXPERT: "Characterise the operating envelope boundary conditions and exception-handling logic.",
        "topic": "exceptions",
        "hint": "Listen for: emergency modes, manual overrides, unusual weather, startup sequences",
    },
    "q21": {
        ReadingLevel.HIGH_SCHOOL: "What do you wish you had known earlier about this system?",
        ReadingLevel.TECHNICAL_COLLEGE: "What lessons learned would you share with someone new to this system?",
        ReadingLevel.PROFESSIONAL: "What institutional knowledge is at risk of being lost and should be documented?",
        ReadingLevel.EXPERT: "What tacit knowledge and lessons learned are not captured in any documentation?",
        "topic": "lessons_learned",
        "hint": "Listen for: undocumented behaviours, tribal knowledge, hidden gotchas",
    },
}

# ---------------------------------------------------------------------------
# Inference rules — keyword -> implied question answers
# ---------------------------------------------------------------------------

INFERENCE_RULES: Dict[str, Dict[str, str]] = {
    "chiller": {"q01":"cooling system / chilled water plant","q14":"requires condenser water, electrical power, cooling tower","q10":"high-energy consumer, dominant HVAC cost"},
    "boiler": {"q01":"heating system / hot water or steam plant","q14":"requires gas/oil, electrical power, water makeup","q09":"combustion safety, pressure relief, low-water cutoff required"},
    "AHU": {"q01":"air handling unit for HVAC distribution","q02":"connects to ductwork, chilled/hot water, OA damper","q12":"filter checks, setpoint resets are recurring tasks"},
    "VFD": {"q01":"variable-frequency drive for motor speed control","q14":"requires electrical power, motor, control signal","q03":"drive faults, overheating, harmonic distortion are common failures"},
    "PLC": {"q01":"programmable logic control system","q14":"requires field I/O, HMI, network, UPS","q09":"safety interlocks must be hardwired, not PLC-only"},
    "SCADA": {"q01":"supervisory control and data acquisition","q02":"connects to PLCs, field devices, historian, operator stations","q05":"operators and engineers are primary stakeholders"},
    "BACnet": {"q02":"BACnet/IP or BACnet/MS-TP network protocol","q13":"BACnet certification and programming expertise required"},
    "Modbus": {"q02":"Modbus TCP or RTU communication protocol","q13":"Modbus register map expertise required"},
    "HIPAA": {"q09":"PHI must be protected; HIPAA audit logging mandatory","q06":"HIPAA compliance is a hard constraint"},
    "OSHA": {"q09":"OSHA life-safety requirements are non-negotiable","q06":"OSHA compliance is a hard constraint"},
    "ASHRAE": {"q06":"ASHRAE standard applies as governing code"},
    "NEC": {"q06":"NEC electrical code compliance required","q09":"electrical safety is a hard constraint"},
    "ISO": {"q06":"ISO standard certification requirement","q07":"ISO KPIs and audit requirements apply"},
    "FDA": {"q06":"FDA 21 CFR compliance required","q09":"GMP/validation requirements are hard constraints"},
    "EPA": {"q06":"EPA environmental compliance required","q09":"EPA reporting and limits are mandatory"},
    "inverter": {"q01":"power conversion / variable-speed drive","q03":"thermal failure, harmonic distortion common failure modes"},
    "compressor": {"q01":"gas or air compression system","q09":"pressure relief and safety shutdown required","q10":"high energy consumer"},
    "pump": {"q01":"fluid transfer / pumping system","q03":"cavitation, seal failure, VFD faults are common failures","q12":"pump rotation checks are recurring tasks"},
    "sensor": {"q02":"field sensing / measurement device","q03":"sensor drift and calibration failure are common issues","q12":"calibration and verification are recurring tasks"},
    "actuator": {"q02":"field control device / valve or damper actuator","q03":"actuator failure, linkage wear are common failures"},
    "DDC": {"q01":"direct digital control system","q13":"DDC programming and calibration expertise required"},
    "energy": {"q07":"energy KPIs: kWh, kBtu, EUI, demand kW","q10":"energy cost is dominant operating expense"},
    "efficiency": {"q07":"efficiency is a primary KPI","q15":"improving efficiency is a key pain point"},
    "maintenance": {"q11":"maintenance time is significant","q12":"PM tasks are recurring operations"},
    "redundancy": {"q14":"redundancy reduces single-point-of-failure risk","q16":"redundancy path is a latent factor"},
    "alarm": {"q03":"alarm conditions indicate failure modes","q04":"alarms are system triggers","q15":"alarm management may be a pain point"},
    "setpoint": {"q04":"setpoints are control triggers","q08":"setpoint resets are dynamic behaviour"},
    "schedule": {"q04":"schedules are control triggers","q12":"scheduled operations are repetitive tasks"},
    "retrofit": {"q19":"this is a retrofit to existing system","q17":"existing conditions may differ from design"},
    "commissioning": {"q11":"commissioning takes significant time","q13":"commissioning expertise is required"},
    "interlock": {"q09":"interlocks are safety-critical","q04":"interlocks are control triggers"},
    "emergency": {"q09":"emergency mode is a safety requirement","q20":"emergency is an exception condition"},
    "network": {"q14":"network connectivity is a dependency","q06":"network security is a constraint"},
    "wireless": {"q02":"wireless communication protocol","q16":"wireless reliability is a latent factor"},
    "cloud": {"q14":"cloud connectivity is a dependency","q06":"data privacy and cybersecurity are constraints"},
    "analytics": {"q07":"analytics feed KPI measurement","q13":"data analytics expertise required"},
    "LEED": {"q06":"LEED certification is a constraint","q07":"LEED points are a KPI"},
    "carbon": {"q07":"carbon emissions are a KPI","q10":"carbon cost is an operating expense"},
    "water": {"q10":"water cost is an operating expense","q07":"water use intensity is a KPI"},
    "solar": {"q01":"solar photovoltaic or thermal generation","q14":"requires utility interconnect, inverter, permits"},
    "generator": {"q14":"emergency generator provides backup power","q20":"generator start is an exception condition"},
    "UPS": {"q14":"UPS provides power ride-through","q09":"UPS protects against power failure safety risk"},
    "redundant": {"q14":"redundant path exists","q16":"redundancy is a latent reliability factor"},
}

# ---------------------------------------------------------------------------
# Simplification vocabulary for reading-level adaptation
# ---------------------------------------------------------------------------

_SIMPLIFY_MAP = {
    "delta-T": "temperature difference",
    "EUI": "energy use per square foot",
    "kBtu": "thousand BTU of energy",
    "kW": "kilowatts of power",
    "kWh": "kilowatt-hours of energy",
    "ASHRAE": "industry energy standard",
    "IPMVP": "measurement and verification protocol",
    "PLR": "part-load ratio",
    "CHW": "chilled water",
    "HW": "hot water",
    "SAT": "supply air temperature",
    "OA": "outside air",
    "VFD": "variable-speed drive",
    "DDC": "digital control system",
    "BAS": "building automation system",
    "HVAC": "heating and cooling system",
    "PLC": "programmable controller",
    "SCADA": "remote monitoring and control",
    "NEC": "electrical code",
    "SIL": "safety integrity level",
    "FMEA": "failure analysis",
}


@dataclass
class InferredAnswer:
    question_id: str = ""
    question_text: str = ""
    inferred_from: str = ""
    answer: str = ""
    confidence: float = 0.5
    reading_level: str = ReadingLevel.HIGH_SCHOOL
    implicit: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class InterviewSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    domain: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    questions_asked: List[str] = field(default_factory=list)
    answers: Dict[str, str] = field(default_factory=dict)
    inferred_answers: List[InferredAnswer] = field(default_factory=list)
    reading_level_detected: str = ReadingLevel.HIGH_SCHOOL
    all_21_covered: bool = False
    knowledge_model: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id, "domain": self.domain,
            "questions_asked": self.questions_asked,
            "answers": self.answers,
            "inferred_answers": [a.to_dict() for a in self.inferred_answers],
            "reading_level_detected": self.reading_level_detected,
            "all_21_covered": self.all_21_covered,
            "knowledge_model": self.knowledge_model,
            "created_at": self.created_at,
        }


class SyntheticInterviewEngine:
    """21-question structured knowledge elicitation with LLM inference."""

    def __init__(self) -> None:
        self._sessions: Dict[str, InterviewSession] = {}

    def create_session(self, domain: str, context: Optional[Dict[str, Any]] = None,
                       reading_level: ReadingLevel = ReadingLevel.HIGH_SCHOOL) -> InterviewSession:
        session = InterviewSession(domain=domain, context=context or {},
                                   reading_level_detected=reading_level.value)
        self._sessions[session.session_id] = session
        return session

    def _get(self, session_id: str) -> InterviewSession:
        s = self._sessions.get(session_id)
        if s is None:
            raise KeyError(f"Session {session_id!r} not found")
        return s

    def next_question(self, session_id: str) -> Optional[Dict[str, Any]]:
        s = self._get(session_id)
        # Find questions not yet asked AND not inferred
        inferred_ids = {a.question_id for a in s.inferred_answers}
        for qid in QUESTION_IDS:
            if qid not in s.questions_asked and qid not in inferred_ids:
                level = s.reading_level_detected
                q_bank = QUESTION_BANK[qid]
                text = q_bank.get(level, q_bank.get(ReadingLevel.HIGH_SCHOOL, ""))
                return {
                    "question_id": qid,
                    "question": text,
                    "reading_level": level,
                    "hint": q_bank.get("hint", ""),
                    "topic": q_bank.get("topic", qid),
                    "progress": f"{len(s.questions_asked)+len(inferred_ids)+1}/21",
                }
        return None

    def answer(self, session_id: str, question_id: str, statement: str) -> Dict[str, Any]:
        s = self._get(session_id)
        s.answers[question_id] = statement
        if question_id not in s.questions_asked:
            s.questions_asked.append(question_id)
        # detect reading level
        s.reading_level_detected = self.detect_reading_level(statement).value
        # infer implicit answers
        inferred = self.infer_from_statement(statement, s.domain)
        new_implicit = 0
        existing_ids = {a.question_id for a in s.inferred_answers} | set(s.questions_asked)
        for inf in inferred:
            if inf.question_id not in existing_ids:
                s.inferred_answers.append(inf)
                existing_ids.add(inf.question_id)
                new_implicit += 1
        # check coverage
        covered = set(s.questions_asked) | {a.question_id for a in s.inferred_answers}
        s.all_21_covered = covered.issuperset(set(QUESTION_IDS))
        nxt = self.next_question(session_id)
        total_covered = len(covered)
        return {
            "answer_recorded": True,
            "implicit_answers_found": new_implicit,
            "next_question": nxt,
            "coverage_pct": round(total_covered / 21 * 100, 1),
            "all_21_covered": s.all_21_covered,
        }

    def infer_from_statement(self, statement: str, domain: str = "") -> List[InferredAnswer]:
        results: List[InferredAnswer] = []
        stmt_lower = statement.lower()
        for keyword, implications in INFERENCE_RULES.items():
            if keyword.lower() in stmt_lower:
                for qid, answer_text in implications.items():
                    if not qid.startswith("q"):
                        continue
                    q_bank = QUESTION_BANK.get(qid, {})
                    q_text = q_bank.get(ReadingLevel.HIGH_SCHOOL, "")
                    conf = 0.8 if keyword.lower() in stmt_lower else 0.5
                    results.append(InferredAnswer(
                        question_id=qid, question_text=q_text,
                        inferred_from=statement[:120],
                        answer=answer_text, confidence=conf,
                        reading_level=self.detect_reading_level(statement).value,
                        implicit=True,
                    ))
        return results

    def detect_reading_level(self, text: str) -> ReadingLevel:
        expert_terms = {"SIL","FMEA","IPMVP","PLR","kBtu","delta-T","enthalpy","commissioning","ASHRAE","ISA","interlock"}
        professional_terms = {"EUI","kWh","setpoint","sequence","VFD","DDC","BAS","SCADA","PLC","algorithm"}
        technical_terms = {"HVAC","OSHA","NEC","efficiency","sensor","actuator","controller","protocol"}
        words = set(text.split())
        if len(words & expert_terms) >= 2:
            return ReadingLevel.EXPERT
        if len(words & professional_terms) >= 2:
            return ReadingLevel.PROFESSIONAL
        if len(words & technical_terms) >= 2:
            return ReadingLevel.TECHNICAL_COLLEGE
        sentences = text.split(".")
        avg_words = len(text.split()) / max(len(sentences), 1)
        if avg_words > 20:
            return ReadingLevel.PROFESSIONAL
        if avg_words > 12:
            return ReadingLevel.HIGH_SCHOOL
        return ReadingLevel.MIDDLE_SCHOOL

    def adapt_to_reading_level(self, text: str, target_level: ReadingLevel) -> str:
        if target_level in (ReadingLevel.HIGH_SCHOOL, ReadingLevel.MIDDLE_SCHOOL, ReadingLevel.ELEMENTARY):
            for technical, simple in _SIMPLIFY_MAP.items():
                text = text.replace(technical, simple)
        return text

    def generate_knowledge_model(self, session_id: str) -> Dict[str, Any]:
        s = self._get(session_id)
        topic_map = {QUESTION_BANK[qid]["topic"]: ans for qid, ans in s.answers.items()
                     if qid in QUESTION_BANK}
        for inf in s.inferred_answers:
            if inf.question_id in QUESTION_BANK:
                topic = QUESTION_BANK[inf.question_id]["topic"]
                if topic not in topic_map:
                    topic_map[topic] = inf.answer
        s.knowledge_model = {
            "system_function": topic_map.get("primary_function",""),
            "connections": topic_map.get("connections",""),
            "failure_modes": topic_map.get("failure_modes",""),
            "kpis": topic_map.get("kpis",""),
            "constraints": topic_map.get("constraints",""),
            "dependencies": topic_map.get("dependencies",""),
            "pain_points": topic_map.get("pain_points",""),
            "safety_compliance": topic_map.get("safety_compliance",""),
            "domain": s.domain,
        }
        return s.knowledge_model

    def get_all_21_status(self, session_id: str) -> Dict[str, Any]:
        s = self._get(session_id)
        covered_direct = set(s.questions_asked)
        covered_inferred = {a.question_id for a in s.inferred_answers}
        all_covered = covered_direct | covered_inferred
        remaining = [qid for qid in QUESTION_IDS if qid not in all_covered]
        return {
            "covered": sorted(covered_direct),
            "inferred": sorted(covered_inferred - covered_direct),
            "remaining": remaining,
            "coverage_pct": round(len(all_covered) / 21 * 100, 1),
        }

    def export_interview(self, session_id: str) -> Dict[str, Any]:
        s = self._get(session_id)
        model = self.generate_knowledge_model(session_id)
        status = self.get_all_21_status(session_id)
        return {
            "session": s.to_dict(),
            "knowledge_model": model,
            "coverage_status": status,
            "all_question_ids": QUESTION_IDS,
            "total_answered": len(s.answers),
            "total_inferred": len(s.inferred_answers),
        }
