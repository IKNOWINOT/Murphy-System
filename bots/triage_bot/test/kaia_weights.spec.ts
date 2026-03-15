import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock all external dependencies that don't exist in this test environment
vi.mock('../_base/bot_base', () => ({
  withBotBase: (_opts: any, fn: any) => fn,
}));
vi.mock('../../orchestration/model_proxy', () => ({
  callModel: vi.fn(async () => ({ data: { confidence: 0.8 } }))
}));
vi.mock('../../orchestration/experience/golden_paths', () => ({
  select_path: vi.fn(async () => null),
  record_path: vi.fn(async () => {}),
}));
vi.mock('../../observability/emit', () => ({
  emit: vi.fn(async () => {}),
}));

import { run, _resetKaiaWeightsCache } from '../triage_bot';

vi.mock('../../../orchestration/model_proxy', () => ({
  callModel: vi.fn(async () => ({ data: { confidence: 0.8 } }))
}));

const fakeKV = { async get(_k:string){ return null; }, async put(_k:string,_v:string){ return; } };

function makeDB(statsJson?: string) {
  const rows: any = {
    bot_capabilities: [
      { bot_name: 'triage_bot', stats_json: statsJson ?? null },
    ],
    budgets: [{ month: new Date().toISOString().slice(0, 7), free_pool_cents: 500 }],
    golden_paths: [],
    audit_events: [],
    ledger: [],
  };
  return {
    prepare(sql: string) {
      const api = {
        args: [] as any[],
        bind: (...args: any[]) => { api.args = args; return api; },
        first: async () => {
          if (/FROM bot_capabilities WHERE bot_name/.test(sql)) {
            return rows.bot_capabilities.find((r:any) => r.bot_name === api.args[0]) ?? null;
          }
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
        run: async () => ({})
      };
      return api;
    }
  };
}

describe('W3-06: Kaia Weights Loader', () => {
  beforeEach(() => { _resetKaiaWeightsCache(); });

  it('test_load_kaia_weights_from_db: valid kaia_mix data → KaiaMixMeta returned in output', async () => {
    const kaiaStats = JSON.stringify({ 'kaia_mix.triage': { veritas: 0.5, vallon: 0.3, kiren: 0.2, veritas_vallon: 0.15, kiren_veritas: 0.1, vallon_kiren: 0.05 } });
    const ctx: any = {
      env: { CLOCKWORK_DB: makeDB(kaiaStats), KV_QUOTA: fakeKV },
      userId: 'u1', tier: 'free', runId: 'r1', startTs: Date.now()
    };
    const input: any = { task: 'route this task', params: { intent_tokens: ['analyze'] }, context: { topic: 'test' } };
    const out = await run(input, ctx);
    // With valid kaia_mix, the weights from DB should be used (veritas: 0.5)
    expect(out.meta.kaiaMix.veritas).toBe(0.5);
    expect(out.meta.kaiaMix.vallon).toBe(0.3);
  });

  it('test_load_kaia_weights_empty_db: no triage_bot row → null returned → default mix used', async () => {
    const dbWithNoTriageBot = {
      prepare(sql: string) {
        const api: any = {
          args: [] as any[],
          bind: (...args: any[]) => { api.args = args; return api; },
          first: async () => {
            if (/FROM bot_capabilities WHERE bot_name/.test(sql)) return null;
            if (/FROM budgets/.test(sql)) return { month: new Date().toISOString().slice(0,7), free_pool_cents: 500 };
            return null;
          },
          get: async () => {
            if (/FROM budgets/.test(sql)) return { month: new Date().toISOString().slice(0,7), free_pool_cents: 500 };
            return null;
          },
          all: async () => { return { results: [] }; },
          run: async () => ({})
        };
        return api;
      }
    };
    const ctx: any = {
      env: { CLOCKWORK_DB: dbWithNoTriageBot, KV_QUOTA: fakeKV },
      userId: 'u1', tier: 'free', runId: 'r2', startTs: Date.now()
    };
    const input: any = { task: 'route this task', params: { intent_tokens: ['analyze'] } };
    const out = await run(input, ctx);
    // No kaia_mix in DB → falls back to default kaiaMix() which has veritas: 0.45
    expect(out.meta.kaiaMix.veritas).toBe(0.45);
  });

  it('test_load_kaia_weights_db_error: DB throws → null returned → no crash, default mix used', async () => {
    const brokenDB = {
      prepare(sql: string) {
        const api: any = {
          bind: (..._args: any[]) => api,
          first: async () => {
            // budgetGuard must succeed; other queries fail
            if (/FROM budgets/.test(sql)) return { month: new Date().toISOString().slice(0,7), free_pool_cents: 500 };
            throw new Error('DB connection failed');
          },
          get: async () => {
            if (/FROM budgets/.test(sql)) return { month: new Date().toISOString().slice(0,7), free_pool_cents: 500 };
            throw new Error('DB connection failed');
          },
          all: async () => { throw new Error('DB connection failed'); },
          run: async () => ({})
        };
        return api;
      }
    };
    const ctx: any = {
      env: { CLOCKWORK_DB: brokenDB, KV_QUOTA: fakeKV },
      userId: 'u1', tier: 'free', runId: 'r3', startTs: Date.now()
    };
    const input: any = { task: 'route this task', params: { intent_tokens: ['analyze'] } };
    // Should not crash
    const out = await run(input, ctx);
    expect(out.meta.kaiaMix).toBeDefined();
    // Default mix should be used
    expect(out.meta.kaiaMix.veritas).toBeGreaterThan(0);
  });

  it('test_load_kaia_weights_caching: DB queried only once within 5 min', async () => {
    _resetKaiaWeightsCache();
    const kaiaStats = JSON.stringify({ 'kaia_mix.triage': { veritas: 0.4, vallon: 0.4, kiren: 0.2, veritas_vallon: 0.1, kiren_veritas: 0.1, vallon_kiren: 0.1 } });
    let queryCount = 0;
    const countingDB = {
      prepare(sql: string) {
        const api: any = {
          args: [] as any[],
          bind: (...args: any[]) => { api.args = args; return api; },
          first: async () => {
            if (/FROM bot_capabilities WHERE bot_name/.test(sql)) {
              queryCount++;
              return { bot_name: 'triage_bot', stats_json: kaiaStats };
            }
            if (/FROM budgets/.test(sql)) return { month: new Date().toISOString().slice(0,7), free_pool_cents: 500 };
            return null;
          },
          get: async () => {
            if (/FROM budgets/.test(sql)) return { month: new Date().toISOString().slice(0,7), free_pool_cents: 500 };
            return null;
          },
          all: async () => { return { results: [] }; },
          run: async () => ({})
        };
        return api;
      }
    };
    const ctx: any = {
      env: { CLOCKWORK_DB: countingDB, KV_QUOTA: fakeKV },
      userId: 'u1', tier: 'free', runId: 'r4', startTs: Date.now()
    };
    const input: any = { task: 'route this task', params: { intent_tokens: ['analyze'] } };
    // Call twice
    await run(input, ctx);
    await run(input, ctx);
    // DB should only be queried once (2nd call hits cache)
    expect(queryCount).toBe(1);
  });
});
