
export function synthesizePrompt(goal:string, template:any, plan:any, verbosity:'short'|'normal'|'verbose'='normal'){
  const sys = `You are a senior planner. You will output strict JSON and never leak secrets.`;
  const short = `Goal: ${goal}. Personas: ${(template.personas||[]).join(', ')}. MVP: ${(template.requirements||[]).slice(0,3).join(', ')}.`;
  const long  = [
    `Goal: ${goal}`,
    `Purpose: ${template.purpose}`,
    `Personas: ${(template.personas||[]).join(', ')}`,
    `Requirements: ${(template.requirements||[]).join('; ')}`,
    `Architecture: ${(template.architecture||[]).join('; ')}`,
    `Acceptance: ${(template.acceptance||[]).join('; ')}`,
    `Risks: ${(template.risks||[]).join('; ')}`
  ].join("\n");
  return { short, long };
}
