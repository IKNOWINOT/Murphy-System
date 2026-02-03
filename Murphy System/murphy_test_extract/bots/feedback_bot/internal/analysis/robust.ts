
export function seasonal(rows:any[], half=3){ return []; } // TODO: implement seasonal EWMA
export function estimatePassProb(rows:any[]){
  const vals = rows.map(r=>r.value).filter(v=>typeof v==='number');
  if (!vals.length) return 0.5;
  const pos = vals.filter(v=>v>0).length / vals.length;
  return 0.4 + 0.6*pos;
}
