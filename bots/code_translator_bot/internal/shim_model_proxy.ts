// src/clockwork/bots/code_translator_bot/internal/shim_model_proxy.ts
// Model proxy: attempts a real model call for code translation, falls back to string-replace if unavailable.
type Msg = { role: 'system'|'user'|'assistant'; content: string };

function langFromFilename(name?: string): string|undefined {
  if (!name) return undefined;
  const m = name.split('.').pop()?.toLowerCase();
  const map: any = { ts:'TypeScript', js:'JavaScript', py:'Python', go:'Go', rs:'Rust', java:'Java', cs:'C#', cpp:'C++' };
  return map[m] || undefined;
}

function fallbackTranslate(p: any) {
  const src = p.source_code || '';
  const src_lang = p.src_lang || langFromFilename(p.filename) || 'unknown';
  const target = p.target_lang || src_lang;
  const intent = p.intent || 'translate';
  const banner = `// code_translator_bot(${intent}) from ${src_lang} to ${target}\n`;
  const after = banner + src.replace(/var /g, 'let ').replace(/==/g, '===');
  const tests = p.filename ? [{ filename: p.filename.replace(/\.[^.]+$/, '.test.' + (p.filename.split('.').pop()||'txt')), content: '// pseudo test for ' + (p.filename||'file'), framework: 'vitest' }] : [];
  return {
    patches: [{ before: src, after, diff: '---before\n+++after\n', filename: p.filename || 'snippet', language: target }],
    tests,
    explain: { summary: `Performed ${intent} on ${src_lang}→${target}`, key_points: ['basic normalization','string-replace fallback'], risks: [] },
    model_powered: false,
  };
}

export async function callModel(args: { profile: 'mini'|'turbo'; messages: Msg[]; json?: boolean; maxTokens?: number }) {
  const user = args.messages.find(m => m.role === 'user')?.content || '{}';
  let payload: any = {}; try { payload = JSON.parse(user); } catch {}
  const p = payload?.input?.params || {};
  const src_lang = p.src_lang || langFromFilename(p.filename) || 'unknown';
  const target = p.target_lang || src_lang;
  const intent = p.intent || 'translate';

  try {
    // Attempt real model call via Workers AI or external proxy
    const modelMessages: Msg[] = [
      { role: 'system', content: `You are an expert code translator and refactoring assistant. Translate or refactor the code as requested. Respond with JSON containing: patches (array of {before, after, diff, filename, language}), tests (array of {filename, content, framework}), explain ({summary, key_points, risks}).` },
      { role: 'user', content: JSON.stringify({ intent, src_lang, target_lang: target, source_code: p.source_code || '', filename: p.filename }) },
    ];
    // callModelReal would be injected from the runtime env; since it's not available here,
    // we fall through to the fallback below.
    throw new Error('no_runtime_model');
  } catch {
    // Offline fallback: use string-replace approach
    const result = fallbackTranslate(p);
    return { result, model_powered: false, usage: { tokens_in: 0, tokens_out: 0, cost_usd: 0, model: 'fallback' } };
  }
}

export async function callModelWithFallback(args: { profile: 'mini'|'turbo'; messages: Msg[]; json?: boolean; maxTokens?: number; callModelReal?: (a:any) => Promise<any> }) {
  const user = args.messages.find(m => m.role === 'user')?.content || '{}';
  let payload: any = {}; try { payload = JSON.parse(user); } catch {}
  const p = payload?.input?.params || {};

  if (args.callModelReal) {
    try {
      const resp = await args.callModelReal({ profile: args.profile, messages: args.messages, json: args.json, maxTokens: args.maxTokens });
      const result = resp?.result || resp?.data || {};
      if (result.patches) {
        return { result: { ...result, model_powered: true }, model_powered: true, usage: resp?.usage || { tokens_in: 0, tokens_out: 0, cost_usd: 0, model: args.profile } };
      }
    } catch { /* fall through to fallback */ }
  }

  // Offline fallback
  const result = fallbackTranslate(p);
  return { result, model_powered: false, usage: { tokens_in: 0, tokens_out: 0, cost_usd: 0, model: 'fallback' } };
}

export { fallbackTranslate };

