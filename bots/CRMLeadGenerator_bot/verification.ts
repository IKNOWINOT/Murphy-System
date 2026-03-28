export type Verification = { email:string; status:'valid'|'risky'|'invalid'|'unknown'; reason?:string; mx?:boolean; smtp?:boolean };

export async function verifyEmails(emails: string[]): Promise<Verification[]> {
  try {
    const ver:any = await import('../../integrations/verification_adapter');
    return await ver.verify(emails);
  } catch {
    return emails.map(e => ({ email:e, status:'unknown' }));
  }
}

export function filterHygiene(list: {email?:string}[], opts?: { dropRole?:boolean, dropDisposable?:boolean }): { keep:any[], dropped:any[] } {
  const keep:any[] = [], dropped:any[] = [];
  const ROLE_RE = /\b(info|support|sales|hello|contact|admin|no-reply|noreply|billing|careers)@/i;
  const DISPOSABLE = /(mailinator|guerrillamail|10minutemail|temp-mail|sharklasers|yopmail)\./i;
  for (const r of (list||[])) {
    const e = String(r.email||'');
    if (!e) { dropped.push({ ...r, reason:'no_email' }); continue; }
    if (opts?.dropRole && ROLE_RE.test(e)) { dropped.push({ ...r, reason:'role_account' }); continue; }
    if (opts?.dropDisposable && DISPOSABLE.test(e)) { dropped.push({ ...r, reason:'disposable' }); continue; }
    keep.push(r);
  }
  return { keep, dropped };
}
