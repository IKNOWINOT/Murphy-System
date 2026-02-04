import { describe, it, expect, vi } from 'vitest';
import { run } from '../swisskiss_loader';

function fakeDB() {
  const rows: Record<string, any[]> = {
    bot_capabilities: [
      { bot_name: 'summarizer_bot', intents_json: JSON.stringify(['summarize', 'digest']), domains_json: JSON.stringify(['docs']) },
    ],
    audit_events: [],
    budgets: [{ month: new Date().toISOString().slice(0, 7), free_pool_cents: 500 }],
    golden_paths: []
  };
  return {
    _rows: rows,
    prepare(sql: string) {
      const api = {
        args: [] as any[],
        bind: (...args: any[]) => { api.args = args; return api; },
        first: async () => {
          if (/FROM budgets/.test(sql)) return rows.budgets[0];
          return null;
        },
        all: async () => {
          if (/FROM bot_capabilities/.test(sql)) return { results: rows.bot_capabilities };
          return { results: [] };
        },
        run: async () => ({ })
      };
      return api;
    },
  };
}

const fakeKV = {
  async get(k: string) { return null; },
  async put(k: string, v: string) { return; },
};

vi.mock('../../../orchestration/model_proxy', () => ({
  callModel: vi.fn(async () => ({ data: { uses_bot_base: true, mentions_canvas: true, missing: [], confidence: 0.96 } }))
}));

describe('swisskiss_loader (bots-only)', () => {
  it('stages module with audit & PR', async () => {
    const ctx: any = { env: { CLOCKWORK_DB: fakeDB(), KV_QUOTA: fakeKV }, userId: 'u1', tier: 'free', runId: 'r1', startTs: Date.now() };
    const input: any = { task: 'manual load', params: { url: 'https://github.com/owner/repo', category: 'nlp', bot_name: 'nlp_kit' } };
    const out = await run(input, ctx);
    expect(out.result.status).toBe('staged_for_review');
    expect(out.result.module_yaml).toBeTruthy();
    expect(typeof out.result.pr).toBe('string');
  });
});
