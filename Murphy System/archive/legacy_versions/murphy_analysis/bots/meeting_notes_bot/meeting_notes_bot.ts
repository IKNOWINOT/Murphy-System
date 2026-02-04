import { Input, Output, validateInput, KaiaMixMeta } from './schema';
import { withBotBase, type Ctx } from '../_base/bot_base';
import { select_path, record_path } from '../../orchestration/experience/golden_paths';
import { emit } from '../../observability/emit';

export const BOT_NAME = 'meeting_notes_bot';

function kaiaMix(): KaiaMixMeta {
  return { veritas: 0.58, vallon: 0.27, kiren: 0.15, veritas_vallon: 0.1566, kiren_veritas: 0.087, vallon_kiren: 0.0405 };
}

function djb2(s:string): number { let h=5381; for (let i=0;i<s.length;i++) h=((h<<5)+h)+s.charCodeAt(i); return h>>>0; }
function hashObj(o:any): number { try { return djb2(JSON.stringify(o)); } catch { return djb2(String(o)); } }

async function ensureTranscript(input: Input): Promise<string> {
  const p = input.params || {};
  if (p.transcript && p.transcript.trim().length > 0) return p.transcript;
  const a = (input.attachments||[]).find(x => x.type==='text' && x.text) || (input.attachments||[]).find(x => x.type==='audio');
  if (a?.type === 'text' && a.text) return a.text;
  if (a?.type === 'audio' && a.url) {
    try {
      const stt:any = await import('../../io/audio_stt');
      const res = await stt.stt(a.url);
      if (res?.text) return String(res.text);
    } catch {}
  }
  return '';
}

export const run = withBotBase({ name: BOT_NAME, cost_budget_ref: 0.012, latency_ref_ms: 2500, S_min: 0.46 }, async (raw: Input, ctx: Ctx): Promise<Output> => {
  const v = validateInput(raw);
  if (!v.ok) {
    return {
      result: { meeting:{}, summary:'', decisions:[], action_items:[], risks:[] },
      confidence: 0,
      meta: { budget: { tier: ctx.tier, pool: 'free' }, gp: { hit: false }, stability: { S: 0, action: 'halt' }, kaiaMix: kaiaMix() },
    };
  }
  const input = v.value;
  const p = input.params || {};
  const transcript = (await ensureTranscript(input)).slice(0, 120_000);
  const title = p.title || 'Meeting';
  const date = p.date || new Date().toISOString();

  // GP key
  const key = {
    bot: BOT_NAME,
    title: title.slice(0, 80),
    date: date.slice(0, 10),
    transcript_hash: hashObj(transcript),
    participants_hash: hashObj(p.participants || []),
    project: input.context?.project, topic: input.context?.topic
  };

  // GP reuse
  const gp = await select_path(ctx.env.CLOCKWORK_DB, key, 10000);
  if ((gp as any)?.hit && (gp as any)?.result) {
    const pk = (gp as any).result;
    return {
      result: pk,
      confidence: (gp as any).confidence ?? 0.94,
      meta: { budget: { tier: ctx.tier, pool: 'gp', cost_usd: (gp as any).cost_usd ?? 0 }, gp: { hit: true, key, spec_id: (gp as any).spec_id }, stability: { S: 0.9, action:'continue' }, kaiaMix: kaiaMix() },
      provenance: 'meeting_notes_bot:gp'
    };
  }

  // Build prompt for model_proxy
  const prompt = [
    { role: 'system', content: 'You are MeetingNotesBot. Return STRICT JSON with keys: meeting{title,date,participants}, summary, decisions[], action_items[], risks[], blockers[], next_meeting{suggested_date,agenda[]}. Keep it concise and specific. Owners must be real names from transcript when available.' },
    { role: 'user', content: JSON.stringify({
        title, date, participants: p.participants || [], transcript, style: p.style || {}
      }) }
  ];

  let data:any = null;
  try {
    const mp:any = await import('../../orchestration/model_proxy');
    const resp = await mp.callModel({ profile: 'mini', messages: prompt as any[], json: true, maxTokens: 900 });
    data = (resp?.data) || resp;
  } catch {
    data = {
      meeting: { title, date, participants: p.participants || [] },
      summary: 'Model unavailable. Minimal notes created.',
      decisions: [],
      action_items: [],
      risks: []
    };
  }

  // Normalize output structure
  const result = {
    meeting: {
      title: String(data?.meeting?.title || title).slice(0, 120),
      date: String(data?.meeting?.date || date).slice(0, 25),
      participants: Array.isArray(data?.meeting?.participants) ? data.meeting.participants.slice(0, 30) : (p.participants || [])
    },
    summary: String(data?.summary || '').slice(0, 8000),
    decisions: Array.isArray(data?.decisions) ? data.decisions.slice(0, 30) : [],
    action_items: Array.isArray(data?.action_items) ? data.action_items.slice(0, 50) : [],
    risks: Array.isArray(data?.risks) ? data.risks.slice(0, 20) : [],
    blockers: Array.isArray(data?.blockers) ? data.blockers.slice(0, 20) : [],
    next_meeting: (data?.next_meeting && typeof data.next_meeting==='object') ? data.next_meeting : undefined
  };

  // HIL trigger: if no action items or summary is too short
  if (!result.action_items.length || result.summary.length < 50) {
    await emit(ctx.env.CLOCKWORK_DB, 'hil.required', { bot: BOT_NAME, reason: 'low_actionability', key });
  }

  await record_path(ctx.env.CLOCKWORK_DB, {
    task_type: BOT_NAME,
    key,
    success: true,
    cost_tokens: 900,
    confidence: 0.93,
    spec: result
  });

  const out: Output = {
    result,
    confidence: 0.93,
    meta: { budget: { tier: ctx.tier, pool: 'free', cost_usd: 0.006 }, gp: { hit: false }, stability: { S: 0, action: 'continue' }, kaiaMix: kaiaMix() },
    provenance: 'meeting_notes_bot:v1.0'
  };
  return out;
});
