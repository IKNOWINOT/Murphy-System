import { describe, it, expect, vi } from 'vitest';
import { run } from '../leadgen_crm_bot';

function fakeDB() {
  const rows: Record<string, any[]> = {
    budgets: [{ month: new Date().toISOString().slice(0, 7), free_pool_cents: 500 }],
    contacts: [], companies: [], deals: [], activities: [], campaigns: [], sequences: [], unsubscribes: [], suppression_events: [], mailbox_state: [],
    golden_paths: [], audit_events: [], lists: [], list_members: []
  };
  return {
    _rows: rows,
    prepare(sql: string) {
      const api = {
        _sql: sql, _args: [] as any[],
        bind: (...args: any[]) => { api._args = args; return api; },
        first: async () => {
          if (/FROM budgets/.test(sql)) return rows.budgets[0];
          if (/FROM unsubscribes WHERE email=/.test(sql)) return null;
          if (/SELECT cursor FROM mailbox_state/.test(sql)) return null;
          if (/COUNT\(\*\) as n FROM contacts/.test(sql)) return { n: rows.contacts.length };
          if (/COUNT\(\*\) as n FROM deals/.test(sql)) return { n: rows.deals.length };
          if (/COUNT\(\*\) as n FROM activities/.test(sql)) return { n: rows.activities.length };
          if (/COUNT\(\*\) as n FROM suppression_events/.test(sql)) return { n: rows.suppression_events.length };
          return null;
        },
        all: async () => {
          if (/SELECT id,email,name/.test(sql)) return { results: rows.contacts };
          if (/FROM golden_paths/.test(sql)) return { results: [] };
          return { results: [] };
        },
        run: async () => {
          if (/INSERT OR REPLACE INTO contacts/.test(sql)) rows.contacts.push({ id: api._args[0], email: api._args[1], name: api._args[2], company: api._args[4] });
          if (/INSERT OR REPLACE INTO companies/.test(sql)) rows.companies.push({ domain: api._args[0], name: api._args[1] });
          if (/INSERT OR REPLACE INTO deals/.test(sql)) rows.deals.push({ id: api._args[0] });
          if (/INSERT INTO activities/.test(sql)) rows.activities.push({ id: api._args[0] });
          if (/INSERT OR REPLACE INTO unsubscribes/.test(sql)) rows.unsubscribes.push({ email: api._args[0] });
          if (/INSERT INTO suppression_events/.test(sql)) rows.suppression_events.push({ email: api._args[1], type: api._args[2] });
          if (/INSERT OR REPLACE INTO mailbox_state/.test(sql)) rows.mailbox_state = [{ id: api._args[0], cursor: api._args[1] }];
          return {};
        }
      };
      return api;
    },
  };
}

const fakeKV = { async get(k:string){ return null; }, async put(k:string,v:string){ return; } };

vi.mock('../../../orchestration/model_proxy', () => ({
  callModel: vi.fn(async ({messages}) => {
    const sys = messages?.[0]?.content || '';
    if (/landing page/i.test(sys)) { return { data: { spec: { sections: ['hero','benefits','cta'] }, html: '<!doctype html><html><body><h1>Landing</h1></body></html>' } }; }
    if (/outbound marketer/i.test(sys)) { return { data: { templates: [{ subject:'Hi', preview:'Quick intro', html:'<p>Hi</p>', text:'Hi'}] } }; }
    if (/variants/.test(sys)) { return { data: { ads: [{ platform:'google', headline:'Try us', body:'Fast', url:'https://example.com'}] } }; }
    return { data: {} };
  })
}));

vi.mock('../../../integrations/verification_adapter', () => ({ verify: vi.fn(async (emails:string[]) => emails.map(e => ({ email:e, status:'valid' }))) }));
vi.mock('../../../io/web_fetch', () => ({ fetchText: vi.fn(async (_url:string) => '<html><body>email: a@ex.com</body></html>' }));
vi.mock('../../../io/html_to_text', () => ({ htmlToText: (h:string) => h.replace(/<[^>]+>/g,' ') }));
vi.mock('../../../integrations/mailbox_adapter', () => ({
  fetchNew: vi.fn(async (_opts:any) => ({ nextCursor: 'cur2', messages: [
    { id:'m1', from:'person1@example.com', text:'Please unsubscribe me' },
    { id:'m2', from:'lead@example.com', text:'Yes let\'s book a demo' },
    { id:'m3', to:'bad@ex.com', text:'Mail delivery failed: undeliverable' }
  ] }))
}));

describe('leadgen_crm_bot v1.2', () => {
  it('discovers and verifies leads from sources', async () => {
    const ctx: any = { env: { CLOCKWORK_DB: fakeDB(), KV_QUOTA: fakeKV }, userId: 'u1', tier: 'free', runId: 'r1', startTs: Date.now() };
    const input: any = { task: 'discover', params: { action:'discover', allow_scrape:true, sources: [{ url:'https://example.com' }] } };
    const out = await run(input, ctx);
    expect(out.result.discovered).toBeGreaterThan(0);
  });
  it('generates assets', async () => {
    const ctx: any = { env: { CLOCKWORK_DB: fakeDB(), KV_QUOTA: fakeKV }, userId: 'u1', tier: 'free', runId: 'r2', startTs: Date.now() };
    const input: any = { task: 'assets', params: { action: 'generate_assets', campaign: { name:'Test', objective:'outbound' } } };
    const out = await run(input, ctx);
    expect(out.result.emails.length).toBeGreaterThan(0);
    expect(out.result.landing.html).toContain('<h1>Landing</h1>');
    expect(out.result.ads.length).toBeGreaterThan(0);
  });
  it('syncs mailbox and handles unsubscribe/positive/bounce', async () => {
    const ctx: any = { env: { CLOCKWORK_DB: fakeDB(), KV_QUOTA: fakeKV }, userId: 'u1', tier: 'free', runId: 'r3', startTs: Date.now() };
    const input: any = { task: 'mailbox', params: { action:'mailbox_sync' } };
    const out = await run(input, ctx);
    expect(out.result.processed).toBe(3);
  });
});
