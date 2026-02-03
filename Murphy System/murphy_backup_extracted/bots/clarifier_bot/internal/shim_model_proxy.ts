// src/clockwork/bots/clarifier_bot/internal/shim_model_proxy.ts
// Minimal clarifier proxy that synthesizes questions from input text for dev/testing.
type Msg = { role: 'system'|'user'|'assistant'; content: string };
export async function callModel(args: { profile: 'mini'|'turbo'; messages: Msg[]; json?: boolean; maxTokens?: number }) {
  const user = args.messages.find(m => m.role === 'user')?.content || '{}';
  let payload: any = {}; try { payload = JSON.parse(user); } catch {}
  const task: string = payload?.input?.task || 'clarify requirements';
  const text = (payload?.input?.attachments || []).map((a:any)=>a.text||'').join(' ').toLowerCase();

  const questions = [];
  const fields = [];

  function pushQ(id: string, field: string, text: string, blocking=false, fmt?:string, example?:string){
    questions.push({ id, field, text, short: text, expected_format: fmt, example, blocking, rationale: `clarifies ${field}` });
    fields.push({ field, required: blocking });
  }

  if (task.toLowerCase().includes('report') || text.includes('report')) {
    pushQ('q1','report_deadline','What is the deadline for the report (YYYY-MM-DD)?', true, 'YYYY-MM-DD','2025-09-30');
    pushQ('q2','report_audience','Who is the primary audience?', true);
  } else {
    pushQ('q1','goal','What is the concrete goal || deliverable?', true);
    pushQ('q2','success_metric','What metric should we use to evaluate success?', true);
  }
  if (text.includes('budget')) pushQ('q3','budget_limit','What is the budget limit (USD)?', false, 'number','500');
  if (text.includes('units')) pushQ('q4','units','Which units should we use (e.g., mm, in)?', false);

  const clarification = {
    questions,
    assumptions:[{ key:'timezone', value:'UTC', confidence:0.6, rationale:'default when unspecified' }],
    missing_fields: fields.filter(f=>f.required).map(f=>f.field),
    priority: 'medium',
    next_steps:[{ id:'t1', title:'Ask blocking questions to user', est_time_min:2 }, { id:'t2', title:'Apply defaults where safe', est_time_min:1 }],
    field_schema: fields
  };

  const result = { clarification };
  return { result, usage: { tokens_in: 180, tokens_out: 160, cost_usd: args.profile==='turbo' ? 0.008 : 0.002, model: args.profile } };
}
