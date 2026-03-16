const EMAIL_RE = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi;
const ROLE_RE = /\b(info|support|sales|hello|contact|admin|no-reply|noreply|billing|careers)@/i;

export type DiscoverSource = { url?: string; html?: string; text?: string; domain_hint?: string };
export type DiscoverResult = { email: string; name?: string; title?: string; company?: string; domain?: string; source?: string };

export async function discoverLeads(sources: DiscoverSource[], adapters: any, options: { allow_scrape?: boolean } = {}): Promise<DiscoverResult[]> {
  const out: DiscoverResult[] = [];
  for (const s of sources) {
    let text = s.text || s.html || '';
    if (!text && s.url) {
      if (!options.allow_scrape) continue;
      try {
        const wf:any = await import('../../io/web_fetch');
        const html = await wf.fetchText(s.url);
        const h2t:any = await import('../../io/html_to_text');
        text = h2t.htmlToText ? h2t.htmlToText(html) : String(html);
      } catch { continue; }
    }
    if (!text) continue;
    const emails = Array.from(new Set(String(text).match(EMAIL_RE) || [])).slice(0, 200);
    for (const e of emails) {
      if (ROLE_RE.test(e)) continue;
      const domain = e.split('@')[1]?.toLowerCase();
      out.push({ email: e, domain, source: s.url || 'pasted', company: s.domain_hint });
    }
  }
  return dedupe(out);
}

function dedupe(arr: DiscoverResult[]): DiscoverResult[] {
  const seen = new Set<string>(); const out: DiscoverResult[] = [];
  for (const a of arr) { const k = a.email.toLowerCase(); if (!seen.has(k)) { seen.add(k); out.push(a); } }
  return out;
}
