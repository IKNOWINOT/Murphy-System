// src/clockwork/bots/code_translator_bot/internal/shim_model_proxy.ts
// Minimal dev proxy: performs trivial "translation/refactor" transforms without external calls.
type Msg = { role: 'system'|'user'|'assistant'; content: string };
function langFromFilename(name?: string): string|undefined {
  if (!name) return undefined;
  const m = name.split('.').pop()?.toLowerCase();
  const map: any = { ts:'TypeScript', js:'JavaScript', py:'Python', go:'Go', rs:'Rust', java:'Java', cs:'C#', cpp:'C++' };
  return map[m] || undefined;
}
export async function callModel(args: { profile: 'mini'|'turbo'; messages: Msg[]; json?: boolean; maxTokens?: number }) {
  const user = args.messages.find(m => m.role === 'user')?.content || '{}';
  let payload: any = {}; try { payload = JSON.parse(user); } catch {}
  const p = payload?.input?.params || {};
  const src = p.source_code || (payload?.input?.attachments||[]).map((a:any)=>a.text||'').join('\n') || '';
  const src_lang = p.src_lang || langFromFilename(p.filename) || 'unknown';
  const target = p.target_lang || src_lang;
  const intent = p.intent || 'translate';
  const banner = `// code_translator_bot(${intent}) from ${src_lang} to ${target}\n`;
  const after = banner + src.replace(/var /g, 'let ').replace(/==/g, '===');

  const tests = p.filename ? [{ filename: p.filename.replace(/\.[^.]+$/, '.test.' + (p.filename.split('.').pop()||'txt')), content: '// pseudo test for ' + (p.filename||'file'), framework: 'vitest' }] : [];

  const result = {
    patches: [{ before: src, after, diff: '---before\n+++after\n', filename: p.filename || 'snippet', language: target }],
    tests,
    explain: { summary: `Performed ${intent} on ${src_lang}→${target}`, key_points: ['basic normalization','placeholder diff'], risks: [] }
  };
  return { result, usage: { tokens_in: 200, tokens_out: 180, cost_usd: args.profile==='turbo' ? 0.009 : 0.0025, model: args.profile } };
}
