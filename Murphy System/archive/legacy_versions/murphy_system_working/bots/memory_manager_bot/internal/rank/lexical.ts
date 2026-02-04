
export function tokenize(s:string){ return (s||'').toLowerCase().split(/[^a-z0-9]+/).filter(Boolean); }
export function lexScore(text:string, query:string){
  const q = tokenize(query); if (!q.length) return 0;
  const t = tokenize(text);
  const set = new Set(t); let hit=0;
  for (const term of q) if (set.has(term)) hit++;
  return hit / q.length;
}
