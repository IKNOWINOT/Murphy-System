
export function costEstimate(spec:any){
  const material=spec.material||'generic', vol=spec.volume_cm3||100, rate=spec.rate_per_hour||50, time_h=spec.time_h||1;
  const material_cost = (material==='ti'?0.03:material==='al'?0.01:0.008)*vol; // $/cm3 heuristic
  return { cost_usd: material_cost + rate*time_h };
}
