import { describe, it, expect, vi } from 'vitest';
import { run } from '../meeting_notes_bot';

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
  callModel: vi.fn(async () => ({
    data: {
      meeting: { title: 'Sprint Review', date: '2025-08-20', participants: ['Alex','Sam'] },
      summary: 'We reviewed progress, agreed to ship v1.2, and identified two risks.',
      decisions: [{ text: 'Ship v1.2 on Friday', owner: 'Alex' }],
      action_items: [{ text: 'Finalize changelog', owner: 'Sam', due: '2025-08-22', priority: 'med' }],
      risks: ['API rate limits']
    }
  }))
}));

describe('meeting_notes_bot', () => {
  it('returns structured notes with decisions and actions', async () => {
    const ctx: any = { env: { CLOCKWORK_DB: fakeDB(), KV_QUOTA: fakeKV }, userId: 'u1', tier: 'free', runId: 'r1', startTs: Date.now() };
    const input: any = {
      task: 'summarize',
      params: { title: 'Sprint Review', date: '2025-08-20', participants: ['Alex','Sam'], transcript: 'Alex: we should ship v1.2. Sam: I will finalize the changelog.' }
    };
    const out = await run(input, ctx);
    expect(out.result.summary.length).toBeGreaterThan(0);
    expect(out.result.decisions.length).toBeGreaterThan(0);
    expect(out.result.action_items.length).toBeGreaterThan(0);
  });

  it('validates input', async () => {
    const ctx: any = { env: { CLOCKWORK_DB: fakeDB(), KV_QUOTA: fakeKV }, userId: 'u2', tier: 'free', runId: 'r2', startTs: Date.now() };
    const out = await run({} as any, ctx);
    expect(out.result.summary).toBe('');
  });
});
