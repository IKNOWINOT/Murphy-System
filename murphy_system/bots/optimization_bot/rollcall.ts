
export default {
  async ping(raw?: any) {
    const t = (raw?.task || "").toLowerCase();
    const kw = ["optimize","bandit","experiment","ab","assign","track","policy","q","bayes","promote","revert"];
    let s = 0; for (const k of kw) if (t.includes(k)) s += 0.16;
    return { can_help: s >= 0.25, confidence: Math.min(1, Math.max(0, s)), est_cost_usd: 0.001, must_have_inputs: [], warnings: [], gp_candidate: undefined, archetype: "vallon_veritas" };
  }
}
