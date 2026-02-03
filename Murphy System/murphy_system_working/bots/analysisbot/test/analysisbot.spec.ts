import { describe, it, expect, vi } from 'vitest';
import { run } from '../analysisbot';

function fakeDB() {
  const rows: Record<string, any[]> = {
    budgets: [{ month: new Date().toISOString().slice(0, 7), free_pool_cents: 500 }],
    golden_paths: [], audit_events: []
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

vi.mock('../../../orchestration/model_proxy', () => ({
  callModel: vi.fn(async ({messages}) => {
    const body = messages?.[1]?.content || '{}';
    const parsed = JSON.parse(body);
    if (messages?.[0]?.content?.includes('SQLResultSummarizer')) {
      return { data: { summary: 'Top categories: A and B.' } };
    }
    // return a safe SELECT
    return { data: { sql: 'SELECT category, COUNT(*) AS n FROM orders GROUP BY 1 ORDER BY n DESC', rationale: 'Group and count by category', warnings: [] } };
  })
}));

vi.mock('../../../io/sql_adapter', () => ({
  getSchema: vi.fn(async (_id:string) => ({ dialect: 'postgres', tables: [{ name:'orders', columns: [{name:'id'},{name:'category'}] }] })),
  execute: vi.fn(async (_id:string, _sql:string, _opts:any) => ({ columns: ['category','n'], rows: [{category:'A', n:10}, {category:'B', n:7}] }))
}));

describe('analysisbot (SQL Analyst upgrade)', () => {
  it('generates safe SQL and (optionally) executes', async () => {
    const ctx: any = { env: { CLOCKWORK_DB: fakeDB(), KV_QUOTA: fakeKV }, userId: 'u1', tier: 'free', runId: 'r1', startTs: Date.now() };
    const input: any = { task: 'How many orders per category?', params: { db: { id:'testdb' }, execute: true, style: { summarize: true } } };
    const out = await run(input, ctx);
    expect(out.result.sql.toLowerCase()).toContain('select');
    expect(out.result.executed).toBe(true);
    expect(out.result.rows?.length).toBeGreaterThan(0);
    expect(out.result.summary?.length).toBeGreaterThan(0);
  });

  it('blocks unsafe SQL and downgrades to dry-run', async () => {
    const ctx: any = { env: { CLOCKWORK_DB: fakeDB(), KV_QUOTA: fakeKV }, userId: 'u2', tier: 'free', runId: 'r2', startTs: Date.now() };
    // mock model to propose DROP (unsafe)
    const mp = await import('../../../orchestration/model_proxy');
    (mp as any).callModel = vi.fn(async () => ({ data: { sql: 'DROP TABLE users', warnings: [] } }));
    const out = await run({ task: 'bad idea', params: { db: { id:'x' }, execute: true } } as any, ctx);
    expect(out.result.executed).toBeFalsy();
    expect(out.result.warnings?.join(',')).toContain('unsafe_sql_blocked');
  });
});
