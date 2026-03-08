import { describe, it, expect } from 'vitest';
import { run } from '../optimization_bot';

function makeDB(runs: any[]) {
  return {
    prepare(sql: string) {
      const api = {
        args: [] as any[],
        bind: (...args: any[]) => { api.args = args; return api; },
        first: async () => {
          if (/FROM budgets/.test(sql)) return { month: new Date().toISOString().slice(0, 7), free_pool_cents: 500 };
          return null;
        },
        get: async () => {
          if (/FROM budgets/.test(sql)) return { month: new Date().toISOString().slice(0, 7), free_pool_cents: 500 };
          return null;
        },
        all: async () => {
          if (/FROM opt_runs/.test(sql)) return { results: runs };
          return { results: [] };
        },
        run: async () => ({})
      };
      return api;
    }
  };
}

const fakeKV = { async get(_k: string) { return null; }, async put(_k: string, _v: string) { } };

describe('W3-08: Optimization Bot Eval Offline', () => {
  it('test_eval_offline_with_real_data: real data → CI computed from actual data, no warning', async () => {
    const runs = [
      ...Array(60).fill(null).map((_, i) => ({ arm_id: 'A', passed: i < 48 ? 1 : 0, reward: i < 48 ? 1 : 0 })),  // 48/60 = 0.8
      ...Array(40).fill(null).map((_, i) => ({ arm_id: 'B', passed: i < 36 ? 1 : 0, reward: i < 36 ? 1 : 0 })),  // 36/40 = 0.9
    ];
    const db = makeDB(runs);
    const ctx: any = { userId: 'u', tier: 'free', db, kv: fakeKV };
    const input: any = { task: 'eval_offline', params: { exp_id: 'exp_test_1' } };
    const out = await run(input, ctx);
    expect(out.result.report).toBeDefined();
    expect(out.result.report.warning).toBeUndefined();
    expect(out.result.report.pass_rate_A).toBeCloseTo(0.8, 1);
    expect(out.result.report.pass_rate_B).toBeCloseTo(0.9, 1);
    expect(out.result.report.n_A).toBe(60);
    expect(out.result.report.n_B).toBe(40);
    expect(out.result.report.uplift).toBeCloseTo(0.1, 1);
    // CI arrays should be valid
    expect(out.result.report.pass_rate_B_ci[0]).toBeGreaterThanOrEqual(0);
    expect(out.result.report.pass_rate_B_ci[1]).toBeLessThanOrEqual(1);
  });

  it('test_eval_offline_no_data_fallback: empty D1 → hardcoded defaults used, warning present', async () => {
    const db = makeDB([]);
    const ctx: any = { userId: 'u', tier: 'free', db, kv: fakeKV };
    const input: any = { task: 'eval_offline', params: { exp_id: 'exp_empty' } };
    const out = await run(input, ctx);
    expect(out.result.report.warning).toBe('no_data_using_defaults');
    expect(out.notes).toContain('no_data_using_defaults');
    // Default uplift is 0.04 (pB=0.64 - pA=0.60)
    expect(out.result.report.uplift).toBeCloseTo(0.04, 2);
  });

  it('test_eval_offline_no_exp_id_fallback: no exp_id → defaults used, warning present', async () => {
    const db = makeDB([]);
    const ctx: any = { userId: 'u', tier: 'free', db, kv: fakeKV };
    const input: any = { task: 'eval_offline', params: {} };
    const out = await run(input, ctx);
    expect(out.result.report.warning).toBe('no_data_using_defaults');
  });

  it('test_eval_offline_db_error_fallback: DB throws → defaults used, no crash', async () => {
    const brokenDB = {
      prepare(sql: string) {
        const api: any = {
          bind: (..._args: any[]) => api,
          first: async () => {
            if (/FROM budgets/.test(sql)) return { month: new Date().toISOString().slice(0,7), free_pool_cents: 500 };
            throw new Error('DB error');
          },
          get: async () => {
            if (/FROM budgets/.test(sql)) return { month: new Date().toISOString().slice(0,7), free_pool_cents: 500 };
            throw new Error('DB error');
          },
          all: async () => { throw new Error('DB error'); },
          run: async () => ({})
        };
        return api;
      }
    };
    const ctx: any = { userId: 'u', tier: 'free', db: brokenDB, kv: fakeKV };
    const input: any = { task: 'eval_offline', params: { exp_id: 'exp_broken' } };
    const out = await run(input, ctx);
    expect(out.result.report).toBeDefined();
    expect(out.result.report.warning).toBe('no_data_using_defaults');
  });
});
