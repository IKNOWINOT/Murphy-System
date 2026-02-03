
function hashStr(s:string, seed=1337){ let h=seed; for (let i=0;i<s.length;i++){ h = (h*31 + s.charCodeAt(i)) >>> 0; } return h>>>0; }
export function rpProject(text:string, dims=64){
  const tokens = (text||'').toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
  const vec = new Array(dims).fill(0);
  for (const t of tokens){
    const h = hashStr(t); for (let i=0;i<dims;i++){ const bit = ((h >>> (i%32)) & 1) ? 1 : -1; vec[i]+=bit; }
  }
  return vec.map(v=> v>=0? '1':'0').join('');
}
export function rpCosine(a:string, b:string){
  if (!a || !b || a.length!==b.length) return 0;
  let dot=0, na=0, nb=0;
  for (let i=0;i<a.length;i++){
    const va = a[i]==='1'?1:-1; const vb = b[i]==='1'?1:-1;
    dot += va*vb; na += va*va; nb += vb*vb;
  }
  return dot / Math.sqrt(na*nb);
}
