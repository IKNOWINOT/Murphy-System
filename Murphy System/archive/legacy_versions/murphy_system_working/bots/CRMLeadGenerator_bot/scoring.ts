export type LeadScore = { score:number; factors: Record<string, number>; grade:'A'|'B'|'C'|'D' };

export function scoreLead(lead: any): LeadScore {
  const f: Record<string, number> = {};
  const title = String(lead.title||'').toLowerCase();
  const domain = String(lead.domain||'').toLowerCase();
  const source = String(lead.source||'').toLowerCase();

  f.role = /(cto|head of|vp|director|founder|engineer|architect|marketing|sales)/.test(title) ? 15 : 5;
  f.domain = domain ? 10 : 0;
  f.company = lead.company ? 10 : 0;
  f.email = /@/.test(String(lead.email||'')) ? 15 : 0;
  f.source = /(inbound|referral|webinar|signup)/.test(source) ? 20 : /(list|scraped)/.test(source) ? 5 : 10;
  f.intent = Array.isArray(lead.tags) && lead.tags.some((t:string)=>/demo|pricing|trial|poc/i.test(t)) ? 20 : 5;
  f.clean = /^[^+]+@[^@]+\.[^@]+$/.test(String(lead.email||'')) ? 5 : 0;

  const score = Math.max(0, Math.min(100, Object.values(f).reduce((a,b)=>a+b, 0)));
  const grade = score>=80?'A':score>=65?'B':score>=50?'C':'D';
  return { score, factors: f, grade };
}
