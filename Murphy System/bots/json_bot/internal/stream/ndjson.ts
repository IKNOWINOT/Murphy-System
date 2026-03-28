
export function parseNDJSON(text:string, maxObjects:number){
  const out:any[]=[]; const lines = text.split(/\r?\n/);
  for (const line of lines){
    const s=line.trim(); if (!s) continue;
    try{ out.push(JSON.parse(s)); }catch{ /* skip malformed */ }
    if (out.length>=maxObjects) break;
  }
  return { items: out, issues: [] as any[], count: out.length };
}
