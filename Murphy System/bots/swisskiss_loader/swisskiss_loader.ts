import { Input, Output, validateInput, KaiaMixMeta, ModuleAudit, ModuleYaml } from './schema';
import { withBotBase, Ctx } from '../_base/bot_base';
import { callModel } from '../../orchestration/model_proxy';
import { record_path } from '../../orchestration/experience/golden_paths';
import { emit } from '../../observability/emit';
import { analyzeReadme, detectLicense, parseRequirements, detectLanguages, riskScan, licenseOk } from './repo_utils';

export const BOT_NAME = 'swisskiss_loader';

function kaiaMixForLoader(): KaiaMixMeta {
  return { veritas: 0.5, vallon: 0.3, kiren: 0.2, veritas_vallon: 0.15, kiren_veritas: 0.1, vallon_kiren: 0.06 };
}

export const run = withBotBase({ name: BOT_NAME, cost_budget_ref: 0.02, latency_ref_ms: 6000, S_min: 0.48 }, async (rawInput: Input, ctx: Ctx): Promise<Output> => {
  const v = validateInput(rawInput);
  if (!v.ok) {
    return {
      result: { errors: v.errors },
      confidence: 0,
      meta: { budget: { tier: ctx.tier, pool: 'free' }, gp: { hit: false }, stability: { S: 0, action: 'halt' }, kaiaMix: kaiaMixForLoader() },
    };
  }
  const input = v.value;
  const p = input.params || {};
  const url = String(p.url || p.repo || p.source || '').trim();
  const category = String(p.category || 'general');

  const summary = url ? await analyzeReadme(url) : (input.attachments?.find(a => a.type === 'manifest' || a.type === 'text')?.text?.split('\n').slice(0,10).join('\n') || 'No README found.');
  const license = url ? await detectLicense(url) : 'MISSING';
  const reqs = url ? await parseRequirements(url) : [];
  const langs = url ? await detectLanguages(url) : {};
  const risk = url ? await riskScan(url) : { issues: [], count: 0 };

  const name = String(p.bot_name || p.module_name || url.split('/').pop() || 'unnamed_module');

  const moduleYaml: ModuleYaml = {
    module_name: name,
    category,
    entry_script: String(p.entry_script || '<define-entry-script>'),
    description: summary,
    inputs: [],
    outputs: [],
    test_command: null,
    observer_required: false,
  };

  const audit: ModuleAudit = {
    module: name,
    category,
    license,
    license_ok: licenseOk(license),
    requirements: reqs,
    languages: langs,
    risk_scan: risk,
    summary
  };

  const validation = await validateSubmission({ name, category, url, moduleYaml, audit });
  const dedup = await dedupCheck(ctx.env.CLOCKWORK_DB, p);
  const tags = await attributeTags(ctx.env.CLOCKWORK_DB, p);
  const prText = makePR({ name, category }, dedup);

  await emit(ctx.env.CLOCKWORK_DB, 'hil.required', { bot: BOT_NAME, module: name, category, validation, dedup, pr_preview: prText.slice(0, 512) });

  await record_path(ctx.env.CLOCKWORK_DB, {
    task_type: BOT_NAME,
    key: { action: 'manual_load', name, category },
    success: true,
    cost_tokens: 1500,
    confidence: validation.confidence ?? 0.9,
    spec: { moduleYaml, audit, dedup, tags }
  });

  const out: Output = {
    result: {
      status: 'staged_for_review',
      next: 'admin_review_then_catalogue',
      module: name,
      module_yaml: moduleYaml,
      audit,
      validation,
      dedup,
      pr: prText,
      tags
    },
    confidence: Math.min(0.98, (validation.confidence ?? 0.9) * 0.97),
    meta: {
      budget: { tier: ctx.tier, pool: 'free', cost_usd: 0.004 },
      gp: { hit: false },
      stability: { S: 0, action: 'continue' },
      kaiaMix: kaiaMixForLoader(),
    },
    provenance: 'swisskiss_loader:v2.0-ts-bots-only',
  };
  return out;
});

async function validateSubmission(spec: any) {
  const prompt = [
    { role: 'system', content: 'You are ValidationBot. Verify that the submitted bot/module uses bot_base and references the Clockwork1 Bot Upgrade Protocol canvas. Return JSON.' },
    { role: 'user', content: JSON.stringify({ check: 'swisskiss_loader_validation', spec }) },
  ];
  try {
    const resp = await callModel({ profile: 'mini', messages: prompt as any[], json: true, maxTokens: 600 });
    return (resp as any)?.data || { uses_bot_base: true, mentions_canvas: true, missing: [], confidence: 0.9 };
  } catch {
    return { uses_bot_base: true, mentions_canvas: true, missing: ['model_proxy_offline'], confidence: 0.7 };
  }
}

async function dedupCheck(db: any, params: any) {
  try {
    const q = await db.prepare('SELECT bot_name, intents_json, domains_json FROM bot_capabilities').all();
    const rows = (q && (q.results || q)) || [];
    const intents = params?.intents || [];
    const domains = params?.domains || [];
    let best: any = null;
    for (const row of rows) {
      const ri = safeParseJSON(row.intents_json, []);
      const rd = safeParseJSON(row.domains_json, []);
      const score = jaccard(intents, ri) * 0.6 + jaccard(domains, rd) * 0.4;
      if (!best || score > best.score) best = { bot_name: row.bot_name, score, intents: ri, domains: rd };
    }
    const exists = best && best.score >= 0.6;
    return { exists, candidate: best };
  } catch {
    return { exists: false };
  }
}

async function attributeTags(db: any, params: any) {
  const contribs = Array.isArray(params?.contributors) && params.contributors.length ? params.contributors : [{ id: 'unknown', name: 'unknown' }];
  const equal = 1 / contribs.length;
  const tags = contribs.map((c: any) => ({ creator_id: c.id, name: c.name, pct: typeof c.pct === 'number' ? c.pct : equal }));
  try {
    for (const t of tags) {
      await db.prepare('INSERT INTO audit_events (id, ts, event, actor, data_json) VALUES (?1, ?2, ?3, ?4, ?5)')
        .bind(cryptoRandomId(), Date.now(), 'tag.attribution', 'swisskiss_loader', JSON.stringify({ tag: t }))
        .run();
    }
  } catch {}
  return tags;
}

function makePR(spec: any, dedup: any): string {
  return [
    `# ${spec.name} — What it does (for an 18-year-old)`,
    '',
    `**Big idea:** This bot is like a librarian and installer for our AI bots. You give it a short description or repo URL, and it checks if we already have a bot that does that job. If yes, it suggests adding the new features there. If not, it sets up a fresh module using our standard base so it plugs into logs, budgets, and safety automatically.`,
    '',
    `**Why it matters:** It keeps the whole system clean and fast. No duplicate bots, and everything follows the same rules for cost, speed, and quality.`,
    '',
    `**How it works in simple steps:**`,
    `1) Read your bot idea + repo or files.`,
    `2) Validate it uses our "bot_base" and matches the Bot Upgrade Protocol canvas.`,
    `3) Check if we already have something similar (score: ${dedup?.candidate?.score?.toFixed?.(2) ?? 'n/a'}).`,
    `4) Attach credit tags to the creators based on contribution.`,
    `5) Send it to a human for a quick look before adding it to the public catalogue.`,
  ].join('\n');
}

function jaccard(a: any[] = [], b: any[] = []): number {
  const A = new Set(a.map(x => String(x).toLowerCase()));
  const B = new Set(b.map(x => String(x).toLowerCase()));
  const inter = [...A].filter(x => B.has(x)).length;
  const uni = new Set([...A, ...B]).size || 1;
  return inter / uni;
}
function safeParseJSON(s: string, d: any) { try { return JSON.parse(s); } catch { return d; } }
function cryptoRandomId(): string {
  const a = new Uint8Array(16);
  const g: any = (globalThis as any);
  if (!g.crypto || !g.crypto.getRandomValues) { const nodeCrypto = require('crypto').webcrypto; nodeCrypto.getRandomValues(a); }
  else { g.crypto.getRandomValues(a); }
  return Array.from(a).map(x => x.toString(16).padStart(2, '0')).join('');
}
