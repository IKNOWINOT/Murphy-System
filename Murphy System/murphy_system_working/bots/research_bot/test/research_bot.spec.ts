import { describe, it, expect, vi } from 'vitest';
import { run } from '../research_bot';

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

vi.mock('../../../orchestration/model_proxy', () => ({
  callModel: vi.fn(async () => ({
    data: {
      answer: 'AI adoption is rising across IT, marketing, and service operations.',
      findings: [{ point: 'Adoption up', quotes: [{ text: '78% use AI in at least one function', source: 'https://example.com' }] }],
      sources: [{ url: 'https://example.com' }]
    }
  }))
}));

describe('research_bot', () => {
  it('synthesizes findings from sources', async () => {
    const ctx: any = { env: { CLOCKWORK_DB: fakeDB(), KV_QUOTA: fakeKV }, userId: 'u1', tier: 'free', runId: 'r1', startTs: Date.now() };
    const input: any = { task: 'What are the top AI use cases?', params: { sources: [{ url: 'https://example.com' }], quote_count: 3 } };
    const out = await run(input, ctx);
    expect(out.result.answer.length).toBeGreaterThan(0);
    expect(out.result.findings.length).toBeGreaterThan(0);
    expect(out.result.sources.length).toBeGreaterThan(0);
  });
});
