const UNSUB_RE = /(unsubscribe|remove|stop|opt\s*out|do\s*not\s*contact)/i;
const POSITIVE_RE = /(interested|let's\s*talk|book|schedule|demo|yes\b)/i;
const BOUNCE_RE = /(delivery\s*status\s*notification|mail delivery failed|undeliverable|mailbox\s*full)/i;

export type InboxMessage = { id:string; from:string; to?:string; subject?:string; text?:string; html?:string; date?:number; inReplyTo?:string; headers?:Record<string,string> };

export async function syncMailbox(adapters:any, cursor: any): Promise<{ nextCursor: any, events: any[] }> {
  const mb:any = await import('../../integrations/mailbox_adapter');
  const { messages, nextCursor } = await mb.fetchNew({ sinceCursor: cursor });
  const events:any[] = [];
  for (const m of (messages || [])) {
    const body = String(m.text || '').slice(0, 5000);
    if (UNSUB_RE.test(body)) events.push({ type:'unsubscribe', email: extractEmail(m.from), id: m.id });
    else if (BOUNCE_RE.test(body)) events.push({ type:'bounce', email: extractEmail(m.to || ''), id: m.id });
    else if (POSITIVE_RE.test(body)) events.push({ type:'positive_reply', email: extractEmail(m.from), id: m.id, snippet: body.slice(0,160) });
    else events.push({ type:'other', id: m.id });
  }
  return { nextCursor, events };
}

function extractEmail(s:string): string {
  const m = String(s||'').match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i);
  return m ? m[0].toLowerCase() : '';
}
