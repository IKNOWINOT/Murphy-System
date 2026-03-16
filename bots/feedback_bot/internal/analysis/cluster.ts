
export function recurring(rows:any[]){
  const key = (r:any)=> `${r.bot}|${r.meta?.category||"general"}`;
  const map = new Map<string, number>();
  for (const r of rows) { const k=key(r); map.set(k,(map.get(k)||0)+1); }
  const out:any[]=[];
  for (const [k,count] of map){ if (count>=3){ const [bot,category]=k.split("|"); out.push({ key:{bot,category}, count }); } }
  return out;
}
