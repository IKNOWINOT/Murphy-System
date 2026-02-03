import { Input, Output, validateInput, KaiaMixMeta } from './schema';
import { withBotBase, type Ctx } from '../_base/bot_base';
import { select_path, record_path } from '../../orchestration/experience/golden_paths';
import { emit } from '../../observability/emit';

// assumed adapters (wired by Codex)
// fetchText(url): Promise<string>; normalizeUrl(url): string
// readPdf(urlOrBytes): Promise<string>
// htmlToText(html): string
// We'll import lazily to avoid bundler issues if absent.
async function lazy(name:string){ return await import(name); }

export const BOT_NAME = 'research_bot';

function kaiaMix(): KaiaMixMeta {
  return { veritas: 0.6, vallon: 0.25, kiren: 0.15, veritas_vallon: 0.15, kiren_veritas: 0.09, vallon_kiren: 0.0375 };
}

function djb2(s:string): number { let h=5381; for (let i=0;i<s.length;i++) h=((h<<5)+h) + s.charCodeAt(i); return h>>>0; }
function hashObj(o:any): number { try{ return djb2(JSON.stringify(o)); } catch { return djb2(String(o)); } }

export const run = withBotBase({ name: BOT_NAME, cost_budget_ref: 0.015, latency_ref_ms: 3500, S_min: 0.48 }, async (raw: Input, ctx: Ctx): Promise<Output> => {
  const v = validateInput(raw);
  if (!v.ok) {
    return {
      result: { answer: '', findings: [], sources: [] },
      confidence: 0,
      meta: { budget: { tier: ctx.tier, pool: 'free' }, gp: { hit: false }, stability: { S: 0, action: 'halt' }, kaiaMix: kaiaMix() },
    };
  }
  const input = v.value;
  const params = input.params || {};
  const max_pages = Math.max(1, Math.min(5, params.max_pages || 3));
  const quote_count = Math.max(2, Math.min(10, params.quote_count || 5));

  const key = {
    bot: BOT_NAME,
    task: input.task.slice(0, 180),
    src_hash: hashObj(params.sources || []),
    style_hash: hashObj(params.style || {}),
    project: input.context?.project, topic: input.context?.topic
  };

  // Golden Path
  const gp = await select_path(ctx.env.CLOCKWORK_DB, key, 10000);
  if ((gp as any)?.hit && (gp as any)?.result) {
    const pk = (gp as any).result;
    return {
      result: pk,
      confidence: (gp as any).confidence ?? 0.93,
      meta: { budget: { tier: ctx.tier, pool: 'gp', cost_usd: (gp as any).cost_usd ?? 0 }, gp: { hit: true, key, spec_id: (gp as any).spec_id }, stability: { S: 0.9, action:'continue' }, kaiaMix: kaiaMix() },
      provenance: 'research_bot:gp'
    };
  }

  // Collect texts
  const sources = Array.isArray(params.sources) ? params.sources.slice(0, max_pages) : [];
  const texts: { url?:string; text:string }[] = [];
  for (const s of sources) {
    if (s?.text && (!s?.url)) { texts.push({ text: s.text }); continue; }
    if (s?.url) {
      try {
        const modFetch:any = await lazy('../../io/web_fetch');
        const norm = modFetch.normalizeUrl ? modFetch.normalizeUrl(s.url) : s.url;
        let body = await modFetch.fetchText(norm);
        if (s.type === 'pdf' || /\.pdf($|\?)/i.test(norm)) {
          const pdf:any = await lazy('../../io/pdf_reader');
          body = await pdf.readPdf(norm);
        } else {
          const h2t:any = await lazy('../../io/html_to_text');
          body = h2t.htmlToText ? h2t.htmlToText(body) : String(body);
        }
        texts.push({ url: norm, text: String(body || '').slice(0, 120_000) });
      } catch {
        // ignore bad source
      }
    }
  }

  const corpus = texts.map(t => ({ url: t.url || 'inline', excerpt: t.text.slice(0, 2000) }));
  const prompt = [
    { role: 'system', content: 'You are ResearchBot. Produce a concise, citation-rich answer in JSON. Always cite with a short quote and url.' },
    { role: 'user', content: JSON.stringify({ question: input.task, corpus, quotes: quote_count, style: params.style || {} }) }
  ];

  // call model_proxy
  let data: any = null;
  try {
    const mp:any = await import('../../orchestration/model_proxy');
    const resp = await mp.callModel({ profile: 'mini', messages: prompt as any[], json: true, maxTokens: 900 });
    data = (resp?.data) || resp;
  } catch {
    data = {
      answer: 'Model unavailable; returning minimal synthesis from sources.',
      findings: corpus.slice(0,2).map(c => ({ point: 'Key point', quotes: [{ text: c.excerpt.slice(0,120), source: c.url }]})),
      sources: corpus.map(c => ({ url: c.url }))
    };
  }

  // Normalize output
  const result = {
    answer: String(data?.answer || '').slice(0, 8000),
    findings: Array.isArray(data?.findings) ? data.findings.slice(0, 8) : [],
    sources: Array.isArray(data?.sources) ? data.sources.slice(0, 8) : (texts.map(t => ({ url: t.url || 'inline' })))
  };

  await record_path(ctx.env.CLOCKWORK_DB, {
    task_type: BOT_NAME,
    key,
    success: true,
    cost_tokens: 1200,
    confidence: 0.92,
    spec: result
  });

  const out: Output = {
    result,
    confidence: 0.92,
    meta: { budget: { tier: ctx.tier, pool: 'free', cost_usd: 0.007 }, gp: { hit: false }, stability: { S: 0, action: 'continue' }, kaiaMix: kaiaMix() },
    provenance: 'research_bot:v1.0'
  };
  return out;
});
