
type Msg = { role: 'system'|'user'|'assistant'; content: string };

function parseEvents(text:string): Array<{ts:string,kind:string,data:any}> {
  const out:any[] = [];
  if (!text) return out;
  for (const line of text.split('\n')){
    const m = line.match(/^\[(.+?)\]\s+(\w+):\s+(.*)$/);
    if (m){ try{ out.push({ ts:m[1], kind:m[2], data: JSON.parse(m[3]) }); }catch{} }
  }
  return out;
}

function summarize(profile:any, events: Array<{ts:string,kind:string,data:any}>){
  const topApp = profile?.active_window || 'Unknown';
  const idleEvents = events.filter(e=>e.kind==='idle').length;
  const ks = (profile?.keystrokes||[]).length;
  const mv = (profile?.mouse_path||[]).length;

  const attention = {
    idle_events: idleEvents,
    avg_idle_s: 0,  // placeholder
    context_switches: events.filter(e=>e.kind==='focus').length,
    top_apps: [{ app: topApp, seconds: 0 }],
    keystroke_rate_hz: ks/Math.max(1,mv+ks)
  };

  // Generate naive steps based on focus + keys
  const steps:any[] = [];
  if (topApp!=='Unknown') steps.push({ id:'s1', action:'focus_app', args:{ app: topApp } });
  steps.push({ id:'s2', action:'wait', args:{ seconds: 0.5 } });
  if (ks>0) steps.push({ id:'s3', action:'type', args:{ text:'<captured text redacted>' } });
  if (mv>5) steps.push({ id:'s4', action:'click', args:{ x: 500, y: 300 } });

  const spec = {
    title: `Automation for ${topApp}`,
    steps,
    triggers: ['on_hotkey:Ctrl+Shift+G'],
    replay_notes: ['Verify element locators before running']
  };

  return { attention, spec };
}

export async function callModel(args: { profile: 'mini'|'turbo'; messages: Msg[]; json?: boolean; maxTokens?: number }) {
  const user = args.messages.find(m => m.role === 'user')?.content || '{}';
  let payload: any = {}; try { payload = JSON.parse(user); } catch {}
  const profile = payload?.input?.profile || {};
  const rawEventsText = (payload?.input?.attachments||[]).find((a:any)=>a.type==='events')?.text || '';
  const events = parseEvents(rawEventsText);

  const { attention, spec } = summarize(profile, events);

  const result = {
    task_summary: `Observed ${events.length} events in ${profile?.active_window || 'Unknown'}; proposing ${spec.steps.length} steps.`,
    automation_spec: spec,
    attention,
    confidence: Math.min(1, 0.8 + Math.min(0.1, events.length/1000))
  };
  return { result, usage: { tokens_in: 220, tokens_out: 220, cost_usd: args.profile==='turbo' ? 0.008 : 0.0025, model: args.profile } };
}
