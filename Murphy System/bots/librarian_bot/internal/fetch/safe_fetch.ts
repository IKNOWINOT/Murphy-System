
export async function safeFetch(url:string, opts:{ allowlist?:string[], timeout_ms?:number, max_bytes?:number } = {}){
  const allow = opts.allowlist||[];
  if (allow.length && !allow.some(dom => url.includes(dom))) throw new Error('remote_not_allowed');
  const ctrl = new AbortController();
  const to = setTimeout(()=>ctrl.abort(), opts.timeout_ms||3000);
  try{
    const r = await fetch(url, { signal: ctrl.signal });
    const buf = new Uint8Array(await r.arrayBuffer());
    if (opts.max_bytes && buf.byteLength>opts.max_bytes) throw new Error('size_limit');
    const text = new TextDecoder().decode(buf);
    return { status:r.status, text };
  } finally { clearTimeout(to); }
}
