# PATCH-383: Murphy Autonomous Engine — simplified version
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List
from enum import Enum

ROLE_PERSONALITY_FIT: Dict[str, Dict[str, float]] = {
    "engineering":     {"openness": 0.6, "conscientiousness": 0.9, "extraversion": 0.3, "agreeableness": 0.5, "neuroticism": 0.1},
    "compliance":      {"openness": 0.4, "conscientiousness": 0.95,"extraversion": 0.3, "agreeableness": 0.6, "neuroticism": 0.05},
    "sales":           {"openness": 0.7, "conscientiousness": 0.7, "extraversion": 0.9, "agreeableness": 0.8, "neuroticism": 0.2},
    "creative":        {"openness": 0.95,"conscientiousness": 0.5, "extraversion": 0.6, "agreeableness": 0.7, "neuroticism": 0.3},
    "finance":         {"openness": 0.5, "conscientiousness": 0.9, "extraversion": 0.4, "agreeableness": 0.5, "neuroticism": 0.05},
    "operations":      {"openness": 0.5, "conscientiousness": 0.85,"extraversion": 0.5, "agreeableness": 0.65,"neuroticism": 0.1},
    "marketing":       {"openness": 0.85,"conscientiousness": 0.65,"extraversion": 0.8, "agreeableness": 0.7, "neuroticism": 0.2},
}

@dataclass
class PersonalityContract:
    openness:           float = 0.5
    conscientiousness:  float = 0.8
    extraversion:       float = 0.5
    agreeableness:      float = 0.6
    neuroticism:        float = 0.1
    persona_label:      str = ""
    communication_style: str = ""
    decision_style:     str = ""
    stress_response:    str = ""
    role_fit_domain:    str = ""

    def compute_fit_score(self, domain: str) -> float:
        ideal = ROLE_PERSONALITY_FIT.get(domain, ROLE_PERSONALITY_FIT["operations"])
        traits = ["openness","conscientiousness","extraversion","agreeableness","neuroticism"]
        dist = sum((getattr(self, t) - ideal[t])**2 for t in traits) ** 0.5
        max_dist = len(traits) ** 0.5
        return round(1.0 - (dist / max_dist), 3)

    def derive_descriptors(self):
        o, c, e, a, n = (self.openness, self.conscientiousness, self.extraversion, self.agreeableness, self.neuroticism)
        if o > 0.8 and c > 0.7: self.persona_label = "Visionary Executor"
        elif o > 0.8: self.persona_label = "Creative Strategist"
        elif c > 0.85 and n < 0.15: self.persona_label = "Precise Analyst"
        elif e > 0.8 and a > 0.7: self.persona_label = "Empathetic Closer"
        elif c > 0.85 and a > 0.7: self.persona_label = "Reliable Partner"
        elif e > 0.7: self.persona_label = "Assertive Driver"
        elif a > 0.8: self.persona_label = "Collaborative Builder"
        elif n < 0.1: self.persona_label = "Calm Authority"
        else: self.persona_label = "Balanced Operator"

        if e > 0.7: self.communication_style = "enthusiastic and direct"
        elif a > 0.75: self.communication_style = "warm and supportive"
        elif c > 0.85 and n < 0.15: self.communication_style = "precise and measured"
        elif o > 0.8: self.communication_style = "abstract and exploratory"
        else: self.communication_style = "professional and balanced"

        if c > 0.8 and n < 0.15: self.decision_style = "data-driven, deliberate"
        elif e > 0.7 and o > 0.7: self.decision_style = "intuitive and bold"
        elif a > 0.8: self.decision_style = "consensus-seeking"
        else: self.decision_style = "systematic, evidence-based"

        if n < 0.1: self.stress_response = "absorbs pressure, maintains precision under ambiguity"
        elif n < 0.2: self.stress_response = "steady — escalates cleanly when blocked"
        elif n < 0.4: self.stress_response = "flags concerns early, seeks validation"
        else: self.stress_response = "requires HITL check-in when stakes are high"

        scores = {d: self.compute_fit_score(d) for d in ROLE_PERSONALITY_FIT}
        self.role_fit_domain = max(scores, key=lambda d: scores[d])

def build_personality_for_role(role_domain: str) -> PersonalityContract:
    ideal = ROLE_PERSONALITY_FIT.get(role_domain, ROLE_PERSONALITY_FIT["operations"])
    p = PersonalityContract(
        openness=ideal["openness"],
        conscientiousness=ideal["conscientiousness"],
        extraversion=ideal["extraversion"],
        agreeableness=ideal["agreeableness"],
        neuroticism=ideal["neuroticism"],
    )
    p.derive_descriptors()
    return p

@dataclass
class AddonCandidate:
    module_name: str
    display_name: str
    description: str
    monthly_price_usd: float
    target_tier: str
    market_rationale: str
    github_branch: str = ""
    lines_of_code: int = 0
    activation_status: str = "pending"
    activation_order: int = 0
    estimated_monthly_revenue: float = 0.0

ADDON_ACTIVATION_QUEUE: List[AddonCandidate] = [
    AddonCandidate("energy_audit_engine","Energy Audit Engine","Automated ASHRAE-grade energy audits",299.0,"business","Zero AI SaaS competition for ASHRAE output",github_branch="copilot/add-engineering-drawing-features",lines_of_code=1325,activation_order=1,estimated_monthly_revenue=2990.0),
    AddonCandidate("cutsheet_engine","Equipment Cut Sheets","Submittals from specs, vendor integration",149.0,"team","Pays for itself on first submittal, natural upsell",github_branch="copilot/add-engineering-drawing-features",lines_of_code=1924,activation_order=2,estimated_monthly_revenue=1490.0),
    AddonCandidate("market_positioning_engine","Market Positioning","Competitor intel, positioning clarity",99.0,"all","Easy add-on, expected 40% adoption rate",github_branch="copilot/mkt-001-create-self-marketing-orchestrator",lines_of_code=1613,activation_order=3,estimated_monthly_revenue=990.0),
    AddonCandidate("client_psychology_engine","Client Psychology Engine","Behavioral profiling for sales",149.0,"team","Amplifies APC, addresses SMB churn vector",github_branch="copilot/mkt-001-create-self-marketing-orchestrator",lines_of_code=1623,activation_order=4,estimated_monthly_revenue=1490.0),
    AddonCandidate("niche_viability_gate","Niche Viability","Business idea validation + 90-day roadmap",49.0,"all","Low-friction first add-on, converts free→paid tenants",github_branch="copilot/analyze-lucrative-niche",lines_of_code=3078,activation_order=5,estimated_monthly_revenue=490.0),
    AddonCandidate("self_marketing_orchestrator","Autonomous Marketing","Content calendar, SEO, social, email A/B",199.0,"team","HubSpot equivalent at 1/10th price",github_branch="copilot/mkt-001-create-self-marketing-orchestrator",lines_of_code=3092,activation_order=6,estimated_monthly_revenue=1990.0),
    AddonCandidate("trading_bot_engine","Treasury Trading","Paper + live algo trading for finance tenants",499.0,"enterprise","$500-2k/mo prosumer tier, treasury amplifier",github_branch="copilot/add-paper-trading-engine-features",lines_of_code=1340,activation_order=7,estimated_monthly_revenue=4990.0),
    AddonCandidate("system_update_recommendation_engine","System Self-Improvement","Internal: Murphy auto-patches itself",0.0,"internal","Closes autonomy loop — critical path",github_branch="copilot/add-founder-maintenance-recommendation-engine",lines_of_code=1734,activation_order=8,estimated_monthly_revenue=0.0),
]

@dataclass
class AutonomyGate:
    gate_id: str
    name: str
    description: str
    status: str
    blocks: List[str]
    patch: str
    priority: int

AUTONOMY_GATES: List[AutonomyGate] = [
    AutonomyGate("G01","LLM Chain","DeepInfra→Together→Ollama fallback","complete",[],  "PATCH-228",1),
    AutonomyGate("G02","CRM + Outreach","APC prospector, SMTP, follow-up sequences","complete",[],"PATCH-195",1),
    AutonomyGate("G03","Billing Infrastructure","NOWPayments, tenant profiles, add-ons","complete",[],"PATCH-381",1),
    AutonomyGate("G04","Scheduling","APScheduler: morning brief, CRM follow-up, prospecting","complete",[],"PATCH-365",1),
    AutonomyGate("G05","Treasury","ATOM staking, bill payment automation","complete",[],"PATCH-378",1),
    AutonomyGate("G06","Payment Gate Enforcement","Block unpaid/expired users from routes","missing",["revenue leakage"],"PATCH-371",1),
    AutonomyGate("G07","Token Ledger","Per-tenant LLM cost tracking, business line attribution","missing",["cannot know true margin per tenant"],"PATCH-367",1),
    AutonomyGate("G08","Self-Healing Loop","autonomous_repair_system wired — Murphy fixes 500s","missing",["silent failures undetected"],"PATCH-383",1),
    AutonomyGate("G09","Observability Stack","Route health, 500 alerting, performance metrics","missing",["no SLA visibility"],"copilot/add-observability-stack",2),
    AutonomyGate("G10","GitHub CI Auto-Activation","Webhook: merged module → auto-wire → test → live","missing",["requires manual intervention"],"PATCH-383",2),
    AutonomyGate("G11","Revenue Recognition","Double-entry accounting from transactions","missing",["no auditable financials"],"PATCH-373",2),
    AutonomyGate("G12","Churn Prediction Model","ML on activity patterns → subscription risk score","missing",["no retention automation"],"PATCH-384",2),
    AutonomyGate("G13","Add-on Auto-Activation","Scanner → rank → wire → test → live pipeline","missing",["add-on activation is manual"],"PATCH-383",2),
    AutonomyGate("G14","Data Isolation","RLS enforced, tenants cannot see each other's data","partial",["compliance risk if violated"],"copilot/arch-003-tenant-isolation",1),
    AutonomyGate("G15","Founder Console","Real-time: revenue, tenant health, gates, costs, errors","partial",["Corey must SSH to see state"],"copilot/arch-007-complete-founder-observability",2),
]

def get_autonomy_status() -> Dict[str, Any]:
    total = len(AUTONOMY_GATES)
    complete  = sum(1 for g in AUTONOMY_GATES if g.status == "complete")
    partial   = sum(1 for g in AUTONOMY_GATES if g.status == "partial")
    missing   = sum(1 for g in AUTONOMY_GATES if g.status == "missing")
    critical_missing = [g for g in AUTONOMY_GATES if g.status == "missing" and g.priority == 1]
    pct = round((complete + partial * 0.5) / total * 100, 1)

    return {
        "autonomy_pct":        pct,
        "gates_complete":      complete,
        "gates_partial":       partial,
        "gates_missing":       missing,
        "total_gates":         total,
        "critical_blockers":   [{"id": g.gate_id, "name": g.name, "patch": g.patch, "blocks": g.blocks} for g in critical_missing],
        "addon_queue": [
            {
                "order":          a.activation_order,
                "module":         a.module_name,
                "display_name":   a.display_name,
                "price":          f"${a.monthly_price_usd:.0f}/mo" if a.monthly_price_usd else "internal",
                "est_revenue":    f"${a.estimated_monthly_revenue:,.0f}/mo at 10 tenants",
                "status":         a.activation_status,
            }
            for a in sorted(ADDON_ACTIVATION_QUEUE, key=lambda x: x.activation_order)
        ],
    }
