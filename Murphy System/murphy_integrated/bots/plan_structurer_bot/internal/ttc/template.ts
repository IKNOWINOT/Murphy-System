
export function makeTemplate(goal:string, answers:any[]){
  const get=(axis:string)=> (answers||[]).filter((a:any)=>a.id?.startsWith(axis)).map((a:any)=>a.value);
  const assumed = (arr:string[])=> arr.map(v => v||'[ASSUMED]');
  const personas = assumed(get('who'));
  const what = assumed(get('what'));
  const why = assumed(get('why'));
  return {
    purpose: `Project: ${goal}`,
    personas,
    scenarios: [],
    requirements: what,
    architecture: assumed(get('how')),
    acceptance: ['Define KPI baselines','Smoke tests passing','MVP demoable'],
    risks: ['Ambiguity around scope','Under-specified non-goals'],
    timeline: assumed(get('when')),
    milestones: ['MVP','Beta','GA'],
    budget: ['[ASSUMED]'],
    success_metrics: why.length?why:['DAU','Latency p50/p95','Error rate']
  };
}
