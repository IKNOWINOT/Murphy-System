import { describe, it, expect, vi } from 'vitest';
import { run } from '../visualization_bot';

function fakeDB() {
  const rows: Record<string, any[]> = {
    budgets: [{ month: new Date().toISOString().slice(0, 7), free_pool_cents: 500 }],
    golden_paths: [], audit_events: [], visuals: []
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
        all: async () => ({ results: [] }),
        run: async () => ({ })
      };
      return api;
    },
  };
}

const fakeKV = { async get(k:string){ return null; }, async put(k:string,v:string){ return; } };

// model_proxy not used here; golden_paths.select_path mocked via DB emptiness

describe('visualization_bot', () => {
  it('builds a bar or line chart spec and validates', async () => {
    const ctx: any = { env: { CLOCKWORK_DB: fakeDB(), KV_QUOTA: fakeKV }, userId: 'u1', tier: 'free', runId: 'r1', startTs: Date.now() };
    const input: any = {
      task: 'Render trend of scores over time',
      params: { kind: 'chart', data: { values: [{ time: '2025-01-01', score: 10 }, { time: '2025-02-01', score: 12 }] }, style: { colorblind_safe: true, show_grid: true } }
    };
    const out = await run(input, ctx);
    expect(out.result.spec_type).toBe('vega-lite');
    expect(out.result.validations.colorblind_safe).toBe(true);
    expect(out.result.validations.misleading_risk).toBeDefined();
  });

  it('produces a technical SVG for cad_scope', async () => {
    const ctx: any = { env: { CLOCKWORK_DB: fakeDB(), KV_QUOTA: fakeKV }, userId: 'u1', tier: 'free', runId: 'r2', startTs: Date.now() };
    const input: any = { task: 'Exploded view', params: { kind: 'cad_scope', data: { parts: [{ id: 'A', w: 100, h: 60 }, { id: 'B', w: 80, h: 50 }] } } };
    const out = await run(input, ctx);
    expect(out.result.spec_type).toBe('svg');
    expect(String(out.result.spec)).toContain('<svg');
  });
});
