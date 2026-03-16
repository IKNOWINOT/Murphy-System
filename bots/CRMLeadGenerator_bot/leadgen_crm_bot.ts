import { Input, Output, validateInput, KaiaMixMeta } from './schema';
import { withBotBase, type Ctx } from '../_base/bot_base';
import { select_path, record_path } from '../../orchestration/experience/golden_paths';
import { emit } from '../../observability/emit';
import { ensureCrm, upsertContact, upsertCompany, createDeal, logActivity, unsubscribe, isUnsubscribed, findContactByEmail, suppressionEvent, getMailboxCursor, setMailboxCursor } from './crm';
import { scoreLead } from './scoring';
import * as assets from './assets';
import { discoverLeads } from './scrub';
import { verifyEmails, filterHygiene } from './verification';
import { syncMailbox } from './mailbox';

export const BOT_NAME = 'leadgen_crm_bot';

function kaiaMix(): KaiaMixMeta {
  return { veritas: 0.6, vallon: 0.25, kiren: 0.15, veritas_vallon: 0.15, kiren_veritas: 0.09, vallon_kiren: 0.0375 };
}
function djb2(s:string): number { let h=5381; for (let i=0;i<s.length;i++) h=((h<<5)+h)+s.charCodeAt(i); return h>>>0; }
function hashObj(o:any): number { try { return djb2(JSON.stringify(o)); } catch { return djb2(String(o)); } }

export const run = withBotBase({ name: BOT_NAME, cost_budget_ref: 0.018, latency_ref_ms: 3200, S_min: 0.48 }, async (raw: Input, ctx: Ctx): Promise<Output> => {
  const v = validateInput(raw);
  if (!v.ok) {
    return { result: { errors: v.errors }, confidence: 0, meta: { budget: { tier: ctx.tier, pool: 'free' }, gp: { hit: false }, stability: { S: 0, action: 'halt' }, kaiaMix: kaiaMix() } };
  }
  const input = v.value; const p = input.params || {};
  await ensureCrm(ctx.env.CLOCKWORK_DB);

  const key = { bot: BOT_NAME, action: p.action || 'ingest', owner: p.owner || input.context?.user_id, task: input.task.slice(0,160),
                hash: hashObj({ leads:p.leads||[], campaign:p.campaign||{}, sequence:p.sequence||{}, assets:p.assets||{}, sources:p.sources||[] }),
                project: input.context?.project, topic: input.context?.topic };

  if (['generate_assets','report','score'].includes(p.action||'')) {
    const gp = await select_path(ctx.env.CLOCKWORK_DB, key, 10000);
    if ((gp as any)?.hit && (gp as any)?.result) {
      return { result: (gp as any).result, confidence: (gp as any).confidence ?? 0.93,
               meta: { budget: { tier: ctx.tier, pool: 'gp', cost_usd: (gp as any).cost_usd ?? 0 }, gp: { hit: true, key, spec_id: (gp as any).spec_id }, stability: { S: 0.9, action:'continue' }, kaiaMix: kaiaMix() },
               provenance: 'leadgen_crm_bot:gp' };
    }
  }

  let result:any = {};
  switch (p.action) {
    case 'discover': result = await actionDiscover(ctx, p); break;
    case 'verify_emails': result = await actionVerify(p); break;
    case 'clean_list': result = await actionCleanList(ctx, p); break;
    case 'mailbox_sync': result = await actionMailboxSync(ctx, p); break;
    case 'opt_in': result = await actionOptIn(ctx, p); break;
    case 'opt_out': result = await actionOptOut(ctx, p); break;
    case 'ingest': result = await actionIngest(ctx, p); break;
    case 'upsert_contact': result = await actionUpsertContact(ctx, p); break;
    case 'upsert_company': result = await actionUpsertCompany(ctx, p); break;
    case 'create_deal': result = await actionCreateDeal(ctx, p); break;
    case 'score': result = await actionScore(ctx, p); break;
    case 'generate_assets': result = await actionGenerateAssets(ctx, p); break;
    case 'enroll': result = await actionEnroll(ctx, p); break;
    case 'launch_campaign': result = await actionLaunchCampaign(ctx, p); break;
    case 'log_activity': result = await actionLogActivity(ctx, p); break;
    case 'search': result = await actionSearch(ctx, p); break;
    case 'unsubscribe': result = await actionUnsubscribe(ctx, p); break;
    case 'report': result = await actionReport(ctx, p); break;
    default:
      result = { note: 'no-op', supported: ['discover','verify_emails','clean_list','mailbox_sync','opt_in','opt_out','ingest','upsert_contact','upsert_company','create_deal','score','generate_assets','enroll','launch_campaign','log_activity','search','unsubscribe','report'] };
  }

  if (['generate_assets','report','score'].includes(p.action||'')) {
    await record_path(ctx.env.CLOCKWORK_DB, { task_type: BOT_NAME, key, success: true, cost_tokens: 1600, confidence: 0.92, spec: result });
  }

  return { result, confidence: 0.92, meta: { budget: { tier: ctx.tier, pool: 'free', cost_usd: 0.01 }, gp: { hit: false }, stability: { S: 0, action:'continue' }, kaiaMix: kaiaMix() }, provenance: 'leadgen_crm_bot:v1.2' };
});

async function actionDiscover(ctx: Ctx, p:any) {
  const sources = Array.isArray(p.sources) ? p.sources : [];
  const leads = await discoverLeads(sources, {}, { allow_scrape: !!p.allow_scrape });
  const ver = await verifyEmails(leads.map(l => l.email));
  const byEmail = new Map(ver.map(v => [v.email.toLowerCase(), v])); const enriched:any[] = [];
  for (const l of leads) {
    const v = byEmail.get(l.email.toLowerCase()); const scored = scoreLead(l);
    const record = { ...l, score: scored.score, grade: scored.grade, verification: v?.status || 'unknown' };
    const existing = await findContactByEmail(ctx.env.CLOCKWORK_DB, l.email);
    if (!existing) await upsertContact(ctx.env.CLOCKWORK_DB, { ...record, source: l.source || 'discover' });
    enriched.push({ lead: record, dedup: !!existing });
  }
  return { discovered: enriched.length, enriched };
}
async function actionVerify(p:any) {
  const emails = (p.leads || []).map((l:any)=>l.email).filter(Boolean);
  const ver = await verifyEmails(emails);
  return { verifications: ver };
}
async function actionCleanList(ctx: Ctx, p:any) {
  const targets = Array.isArray(p.leads) ? p.leads : [];
  const { keep, dropped } = filterHygiene(targets, { dropRole: true, dropDisposable: true });
  const final:any[] = [];
  for (const t of keep) {
    if (t.email && await isUnsubscribed(ctx.env.CLOCKWORK_DB, t.email)) dropped.push({ ...t, reason:'unsubscribed' });
    else final.push(t);
  }
  return { keep: final, dropped };
}
async function actionMailboxSync(ctx: Ctx, p:any) {
  const cursor = await getMailboxCursor(ctx.env.CLOCKWORK_DB, p?.mailbox_id || 'default');
  const { nextCursor, events } = await syncMailbox({}, cursor);
  for (const ev of events) {
    if (ev.type === 'unsubscribe' && ev.email) { await unsubscribe(ctx.env.CLOCKWORK_DB, ev.email, 'email_request'); }
    else if (ev.type === 'bounce' && ev.email) { await suppressionEvent(ctx.env.CLOCKWORK_DB, ev.email, 'bounce', {}); }
    else if (ev.type === 'positive_reply' && ev.email) {
      const existing = await findContactByEmail(ctx.env.CLOCKWORK_DB, ev.email);
      if (existing?.id) await logActivity(ctx.env.CLOCKWORK_DB, existing.id, { type:'reply', notes: ev.snippet || 'positive reply' });
    }
  }
  await setMailboxCursor(ctx.env.CLOCKWORK_DB, nextCursor || cursor, p?.mailbox_id || 'default');
  return { processed: events.length, nextCursor };
}
async function actionOptIn(ctx: Ctx, p:any) {
  const email = p?.contact?.email; if (!email) return { error: 'email_required' };
  await ctx.env.CLOCKWORK_DB.prepare('DELETE FROM unsubscribes WHERE email=?1').bind(email).run();
  await suppressionEvent(ctx.env.CLOCKWORK_DB, email, 'opt_in', {});
  return { opted_in: email };
}
async function actionOptOut(ctx: Ctx, p:any) {
  if (!p?.contact?.email) return { error: 'email_required' };
  await unsubscribe(ctx.env.CLOCKWORK_DB, p.contact.email, p?.reason || 'user_request');
  return { opted_out: p.contact.email };
}
async function actionIngest(ctx: Ctx, p:any) {
  const leads:any[] = Array.isArray(p.leads) ? p.leads : parseCsv(p?.data?.csv || '');
  const enriched:any[] = [];
  for (const l of leads) {
    let enrichedLead:any = { ...l };
    try { const enr:any = await import('../../integrations/enrichment_adapter');
          const res = await enr.enrich({ email: l.email, domain: l.domain || (l.email||'').split('@')[1] });
          enrichedLead = { ...l, ...(res?.person||{}), company: l.company || res?.company?.name, domain: l.domain || res?.company?.domain }; } catch {}
    const score = scoreLead(enrichedLead); enrichedLead.score = score.score; enrichedLead.grade = score.grade;
    const existing = enrichedLead.email ? await findContactByEmail(ctx.env.CLOCKWORK_DB, enrichedLead.email) : null;
    if (!existing) { await upsertContact(ctx.env.CLOCKWORK_DB, { ...enrichedLead, tags: l.tags||[], source: l.source||'ingest' });
                     if (enrichedLead.domain) await upsertCompany(ctx.env.CLOCKWORK_DB, { domain: enrichedLead.domain, name: enrichedLead.company }); }
    enriched.push({ lead: enrichedLead, dedup: !!existing });
  }
  return { ingested: enriched.length, enriched };
}
async function actionUpsertContact(ctx: Ctx, p:any) {
  const c = p.contact || {}; const score = scoreLead(c);
  const id = await upsertContact(ctx.env.CLOCKWORK_DB, { ...c, score: score.score, grade: score.grade });
  return { contact_id: id, score };
}
async function actionUpsertCompany(ctx: Ctx, p:any) { const domain = await upsertCompany(ctx.env.CLOCKWORK_DB, p.company || {}); return { domain }; }
async function actionCreateDeal(ctx: Ctx, p:any) { const id = await createDeal(ctx.env.CLOCKWORK_DB, p.deal || {}); return { deal_id: id }; }
async function actionScore(ctx: Ctx, p:any) { const leads = p.leads || (p.contact ? [p.contact] : []); return leads.map((l:any)=>({ email:l.email, score: scoreLead(l) })); }
async function actionGenerateAssets(ctx: Ctx, p:any) {
  let templates:any[] = [], landing:any = {}, ads:any[] = [];
  try { const mp:any = await import('../../orchestration/model_proxy'); const tone = p.style?.tone || 'persuasive';
        templates = await assets.buildEmailTemplates(mp, tone, p.campaign || {}, 3);
        landing = await assets.buildLandingSpec(mp, tone, p.campaign || {});
        ads = await assets.buildAdCopy(mp, tone, p.campaign || {}); }
  catch { templates = [{ subject:'Hello', preview:'Quick intro', html:'<p>Hi</p>', text:'Hi' }];
          landing = { spec:{}, html:'<!doctype html><html><body><h1>Landing</h1></body></html>' };
          ads = [{ platform:'google', headline:'Try us', body:'Fast, simple, powerful', url:'https://example.com' }]; }
  return { emails: templates, landing, ads };
}
async function actionEnroll(ctx: Ctx, p:any) {
  const seq = p.sequence || { steps: [] };
  const targets = Array.isArray(p.leads) ? p.leads : (p.contact ? [p.contact] : []);
  const scheduled:any[] = [];
  for (const t of targets) {
    if (t.email && await isUnsubscribed(ctx.env.CLOCKWORK_DB, t.email)) { scheduled.push({ target: t.email, skipped: 'unsubscribed' }); continue; }
    let delaySum = 0;
    for (const step of seq.steps || []) {
      delaySum += Math.max(0, step.delay_h||0);
      const when = Date.now() + delaySum*3600*1000;
      const plan = { to: t.email || t.phone, channel: step.channel, when, template_id: step.template_id, copy: step.copy, campaign_id: p?.campaign?.id };
      if (p.execute) await sendPlan(plan);
      scheduled.push({ ...plan, scheduled: !p.execute, sent: !!p.execute });
    }
  }
  return { scheduled };
}
async function actionLaunchCampaign(ctx: Ctx, p:any) {
  const plans:any[] = []; const targets = p.leads || [];
  const campaignId = p?.campaign?.id || 'cmp_'+Math.random().toString(16).slice(2);
  let track:any = null; try { const tr:any = await import('../../integrations/tracking_adapter'); track = tr; } catch {}
  for (const l of targets) {
    if (l.email && await isUnsubscribed(ctx.env.CLOCKWORK_DB, l.email)) { continue; }
    const subject = `Quick question for ${l.company || l.name || 'you'}`;
    let body = `Hi ${l.name||''}, curious if ${l.company||'your team'} is exploring this?`;
    if (track?.createTrackingLinks) { const mapped = await track.createTrackingLinks([{ url: p?.campaign?.utm?.url || 'https://example.com' }], campaignId);
                                      const url = mapped?.[0]?.url || 'https://example.com'; body += `\n\nMore details: ${url}`; }
    const plan = { to: l.email, channel: 'email', campaign_id: campaignId, copy: { subject, body } };
    if (p.execute) await sendPlan(plan); plans.push({ ...plan, scheduled: !p.execute, sent: !!p.execute });
  }
  return { campaign_id: campaignId, plans };
}
async function actionLogActivity(ctx: Ctx, p:any) {
  const cid = p?.contact?.id || (p?.contact?.email ? (await findContactByEmail(ctx.env.CLOCKWORK_DB, p.contact.email))?.id : null);
  if (!cid) return { error: 'contact_not_found' };
  const id = await logActivity(ctx.env.CLOCKWORK_DB, cid, p.activity || {});
  return { activity_id: id };
}
async function actionSearch(ctx: Ctx, p:any) {
  const q = (p.filters && p.filters.q) ? String(p.filters.q).toLowerCase() : '';
  const res = await ctx.env.CLOCKWORK_DB.prepare('SELECT id,email,name,title,company,domain,owner,score,grade FROM contacts').all();
  const rows = (res?.results || []).filter((r:any)=>!q || String(r.email||'').toLowerCase().includes(q) || String(r.name||'').toLowerCase().includes(q) || String(r.company||'').toLowerCase().includes(q));
  return { contacts: rows.slice(0, 200) };
}
async function actionUnsubscribe(ctx: Ctx, p:any) { if (!p?.contact?.email) return { error: 'email_required' }; await unsubscribe(ctx.env.CLOCKWORK_DB, p.contact.email, p?.reason || 'user_request'); return { unsubscribed: p.contact.email }; }
async function actionReport(ctx: Ctx, p:any) {
  const contacts = await ctx.env.CLOCKWORK_DB.prepare('SELECT COUNT(*) as n FROM contacts').first();
  const deals = await ctx.env.CLOCKWORK_DB.prepare('SELECT COUNT(*) as n FROM deals').first();
  const activities = await ctx.env.CLOCKWORK_DB.prepare('SELECT COUNT(*) as n FROM activities').first();
  const suppressions = await ctx.env.CLOCKWORK_DB.prepare('SELECT COUNT(*) as n FROM suppression_events').first();
  return { totals: { contacts: contacts?.n||0, deals: deals?.n||0, activities: activities?.n||0, suppression_events: suppressions?.n||0 } };
}

async function sendPlan(plan:any) {
  try {
    if (plan.channel === 'email') { const em:any = await import('../../integrations/email_adapter');
      await em.sendEmail({ to: plan.to, subject: plan.copy?.subject || 'Hello', html: plan.copy?.body || '<p>Hello</p>', text: plan.copy?.text, campaign_id: plan.campaign_id });
    } else if (plan.channel === 'sms') { const sms:any = await import('../../integrations/sms_adapter');
      await sms.sendSms({ to: plan.to, text: plan.copy?.text || 'Hello', campaign_id: plan.campaign_id });
    } else if (plan.channel === 'social') { const soc:any = await import('../../integrations/social_adapter');
      await soc.send({ platform: 'linkedin', to: plan.to, message: plan.copy?.text || 'Hello', campaign_id: plan.campaign_id });
    }
  } catch {}
}
function parseCsv(csv:string): any[] {
  if (!csv) return []; const lines = csv.split(/\r?\n/).filter(Boolean); const headers = (lines.shift() || '').split(',').map(s=>s.trim());
  return lines.map(line => { const cells = line.split(','); const o:any = {}; headers.forEach((h,i)=>o[h]=cells[i]); return o; });
}
