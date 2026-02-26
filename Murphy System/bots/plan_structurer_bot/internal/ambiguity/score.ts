
export function ambiguityScore(goal:string){
  const len = (goal||'').trim().split(/\s+/).length;
  const vague = /(something|stuff|etc|like|similar|whatever|make me|build me)/i.test(goal||'');
  const specificity = /(deadline|budget|platform|api|stack|region|slo|kpi|metrics|users|personas)/i.test(goal||'');
  let score = 0.5 + (vague?0.2:0) - (specificity?0.3:0) - Math.min(0.2, Math.max(0, (len-12)/50));
  return Math.max(0, Math.min(1, score)); // 1=very ambiguous
}
