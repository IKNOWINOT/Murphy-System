import { describe, it, expect, vi } from 'vitest';

// Mock external dependencies that don't exist in test environment
vi.mock('../_base/bot_base', () => ({
  withBotBase: (_opts: any, fn: any) => fn,
}));
vi.mock('../../orchestration/experience/golden_paths', () => ({
  select_path: vi.fn(async () => null),
  record_path: vi.fn(async () => {}),
}));
vi.mock('../../observability/emit', () => ({
  emit: vi.fn(async () => {}),
}));

import { run } from '../triage_bot';

function fakeDB() {
  const rows: Record<string, any[]> = {
    bot_capabilities: [
      { bot_name: 'AnalysisBot', intents_json: JSON.stringify(['analyze','triage','classify']), domains_json: JSON.stringify(['nlp','docs']), stats_json: JSON.stringify({ gp_pass_rate: 0.9, gp_runs: 30, S_hist: [0.7,0.8,0.75], avg_cost_usd: 0.004, avg_latency_ms: 1500 }) },
      { bot_name: 'EngineeringBot', intents_json: JSON.stringify(['build','code','api']), domains_json: JSON.stringify(['backend','infra']), stats_json: JSON.stringify({ gp_pass_rate: 0.6, gp_runs: 10, S_hist: [0.6,0.55], avg_cost_usd: 0.006, avg_latency_ms: 2200 }) },
    ],
    budgets: [{ month: new Date().toISOString().slice(0, 7), free_pool_cents: 500 }],
    golden_paths: [],
    audit_events: [],
    ledger: [],
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
        get: async () => {
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

const fakeKV = { async get(k:string){ return null; }, async put(k:string,v:string){ return; } };

vi.mock('../../../orchestration/model_proxy', () => ({
  callModel: vi.fn(async ({messages}) => ({ data: { confidence: messages?.[1]?.content?.includes('EngineeringBot') ? 0.7 : 0.9 } }))
}));

describe('triage_bot', () => {
  it('ranks candidates and assigns', async () => {
    const ctx: any = { env: { CLOCKWORK_DB: fakeDB(), KV_QUOTA: fakeKV }, userId: 'u1', tier: 'free', runId: 'r1', startTs: Date.now() };
    const input: any = { task: 'Please triage and analyze our docs', params: { intent_tokens: ['triage','analyze'] }, context: { topic: 'nlp' } };
    const out = await run(input, ctx);
    expect(out.result.status).toBe('assigned');
    expect(out.result.chosen_bot).toBe('AnalysisBot');
    expect(out.meta.kaiaMix.veritas).toBeGreaterThan(0.4);
  });

  it('validates input', async () => {
    const ctx: any = { env: { CLOCKWORK_DB: fakeDB(), KV_QUOTA: fakeKV }, userId: 'u1', tier: 'free', runId: 'r2', startTs: Date.now() };
    const out = await run({} as any, ctx);
    expect(out.result.errors).toBeTruthy();
  });
});
