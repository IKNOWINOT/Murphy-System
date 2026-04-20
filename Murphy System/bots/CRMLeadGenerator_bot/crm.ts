// @ts-ignore — optional Node.js crypto fallback for environments without Web Crypto API
import nodeCrypto from 'crypto';

export async function ensureCrm(db:any) {
  const stmts = [`
    CREATE TABLE IF NOT EXISTS contacts (
      id TEXT PRIMARY KEY, email TEXT UNIQUE, name TEXT, title TEXT, company TEXT, domain TEXT, phone TEXT,
      owner TEXT, source TEXT, tags_json TEXT, custom_json TEXT, score INTEGER, grade TEXT, created_ts INTEGER, updated_ts INTEGER
    );
  `,`
    CREATE TABLE IF NOT EXISTS companies ( domain TEXT PRIMARY KEY, name TEXT, size TEXT, industry TEXT, updated_ts INTEGER );
  `,`
    CREATE TABLE IF NOT EXISTS deals ( id TEXT PRIMARY KEY, company_domain TEXT, title TEXT, amount REAL, stage TEXT, pipeline TEXT, owner TEXT, created_ts INTEGER, updated_ts INTEGER );
  `,`
    CREATE TABLE IF NOT EXISTS activities ( id TEXT PRIMARY KEY, contact_id TEXT, type TEXT, notes TEXT, ts INTEGER, meta_json TEXT );
  `,`
    CREATE TABLE IF NOT EXISTS campaigns ( id TEXT PRIMARY KEY, name TEXT, objective TEXT, utm_json TEXT, created_ts INTEGER );
  `,`
    CREATE TABLE IF NOT EXISTS sequences ( id TEXT PRIMARY KEY, name TEXT, steps_json TEXT, created_ts INTEGER );
  `,`
    CREATE TABLE IF NOT EXISTS unsubscribes ( email TEXT PRIMARY KEY, ts INTEGER, reason TEXT );
  `,`
    CREATE TABLE IF NOT EXISTS suppression_events ( id TEXT PRIMARY KEY, email TEXT, type TEXT, ts INTEGER, meta_json TEXT );
  `,`
    CREATE TABLE IF NOT EXISTS lists ( id TEXT PRIMARY KEY, name TEXT, created_ts INTEGER );
  `,`
    CREATE TABLE IF NOT EXISTS list_members ( list_id TEXT, email TEXT, added_ts INTEGER, PRIMARY KEY(list_id, email) );
  `,`
    CREATE TABLE IF NOT EXISTS mailbox_state ( id TEXT PRIMARY KEY, cursor TEXT, updated_ts INTEGER );
  `];
  for (const s of stmts) { try { await db.prepare(s).run(); } catch (e) { console.warn('CRM schema init warning:', e); } }
}

export async function upsertContact(db:any, c:any) {
  const id = c.id || cryptoId();
  const now = Date.now();
  await db.prepare(`INSERT OR REPLACE INTO contacts
    (id,email,name,title,company,domain,phone,owner,source,tags_json,custom_json,score,grade,created_ts,updated_ts)
    VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,COALESCE(?12,0),COALESCE(?13,''),COALESCE(?14,?15),?16)`)
    .bind(id,c.email||null,c.name||null,c.title||null,c.company||null,c.domain||null,c.phone||null,c.owner||null,c.source||null,
          JSON.stringify(c.tags||[]), JSON.stringify(c.custom||{}), c.score||0, c.grade||'', c.created_ts||now, now).run();
  return id;
}
export async function upsertCompany(db:any, comp:any) {
  await db.prepare(`INSERT OR REPLACE INTO companies (domain,name,size,industry,updated_ts) VALUES (?1,?2,?3,?4,?5)`)
    .bind(comp.domain||null, comp.name||null, comp.size||null, comp.industry||null, Date.now()).run();
  return comp.domain;
}
export async function createDeal(db:any, d:any) {
  const id = d.id || cryptoId();
  await db.prepare(`INSERT OR REPLACE INTO deals (id, company_domain, title, amount, stage, pipeline, owner, created_ts, updated_ts)
    VALUES (?1,?2,?3,?4,?5,?6,?7, COALESCE(?8,?9), ?10)`)
    .bind(id, d.company_domain||null, d.title||null, d.amount||null, d.stage||'new', d.pipeline||'default', d.owner||null, d.created_ts||Date.now(), Date.now(), Date.now()).run();
  return id;
}
export async function logActivity(db:any, contact_id:string, act:any) {
  const id = cryptoId();
  await db.prepare(`INSERT INTO activities (id, contact_id, type, notes, ts, meta_json) VALUES (?1,?2,?3,?4,?5,?6)`)
    .bind(id, contact_id, act.type||'note', String(act.notes||''), act.ts||Date.now(), JSON.stringify(act.meta||{})).run();
  return id;
}
export async function unsubscribe(db:any, email:string, reason:string='user_request') {
  await db.prepare(`INSERT OR REPLACE INTO unsubscribes (email, ts, reason) VALUES (?1, ?2, ?3)`).bind(email, Date.now(), reason).run();
  await db.prepare(`INSERT INTO suppression_events (id, email, type, ts, meta_json) VALUES (?1,?2,?3,?4,?5)`)
    .bind(cryptoId(), email, 'unsubscribe', Date.now(), JSON.stringify({reason})).run();
}
export async function suppressionEvent(db:any, email:string, type:string, meta:any={}) {
  await db.prepare(`INSERT INTO suppression_events (id, email, type, ts, meta_json) VALUES (?1,?2,?3,?4,?5)`)
    .bind(cryptoId(), email, type, Date.now(), JSON.stringify(meta)).run();
}
export async function isUnsubscribed(db:any, email:string) {
  const row = await db.prepare('SELECT email FROM unsubscribes WHERE email=?1').bind(email).first();
  return !!row;
}
export async function findContactByEmail(db:any, email:string) {
  return await db.prepare('SELECT * FROM contacts WHERE email=?1').bind(email).first();
}
export async function getMailboxCursor(db:any, id='default') {
  const row = await db.prepare('SELECT cursor FROM mailbox_state WHERE id=?1').bind(id).first();
  return row?.cursor || null;
}
export async function setMailboxCursor(db:any, cursor:string, id='default') {
  await db.prepare('INSERT OR REPLACE INTO mailbox_state (id, cursor, updated_ts) VALUES (?1, ?2, ?3)').bind(id, cursor, Date.now()).run();
}
function cryptoId(): string {
  const a = new Uint8Array(16); const g:any = (globalThis as any);
  if (!g.crypto || !g.crypto.getRandomValues) { nodeCrypto.webcrypto.getRandomValues(a); }
  else { g.crypto.getRandomValues(a); }
  return Array.from(a).map(x => x.toString(16).padStart(2, '0')).join('');
}
