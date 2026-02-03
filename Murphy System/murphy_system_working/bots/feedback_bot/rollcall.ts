
export default {
  async ping(raw?: any) {
    const t = (raw?.task || "").toLowerCase();
    const kw = ["feedback","score","decay","reinforcement","bandit","recurring","improvement","prompt","remediation","gp"];
    let s = 0; for (const k of kw) if (t.includes(k)) s += 0.16;
    return { can_help: s >= 0.25, confidence: Math.min(1, Math.max(0, s)), est_cost_usd: 0.002, must_have_inputs: [], warnings: [], gp_candidate: undefined, archetype: "veritas_vallon" };
  }
}
