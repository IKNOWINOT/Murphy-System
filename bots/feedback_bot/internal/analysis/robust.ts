
export function seasonal(rows:any[], half=3){
  const now = Date.now(); const day=86400e3; const out:any[]=[]; const group = new Map<string, any[]>();
  for (const r of rows){ const k = `${r.bot}|${r.task_type||""}|${r.meta?.gp_id||""}`; (group.get(k) ?? group.set(k,[]).get(k)).push(r); }
  for (const [k, arr] of group){
    // Bucket events by day-of-week (0-6)
    const buckets: number[][] = Array.from({length:7}, ()=>[]);
    for (const e of arr){
      const dow = new Date(e.ts).getDay();
      buckets[dow].push(e.value||0);
    }
    // Compute per-bucket mean for seasonal index (only non-empty buckets contribute)
    const bucketMean = buckets.map(b => b.length ? b.reduce((s,v)=>s+v,0)/b.length : 0);
    const nonZeroMeans = bucketMean.filter(v=>v!==0);
    const overallMean = nonZeroMeans.length ? nonZeroMeans.reduce((s,v)=>s+v,0)/nonZeroMeans.length : 0;
    const seasonalIndex = buckets.map((b,i) => overallMean > 0 ? bucketMean[i]/overallMean : 1);
    // Compute EWMA level over all events (time-ordered)
    const sorted = arr.slice().sort((a,b)=>new Date(a.ts).getTime()-new Date(b.ts).getTime());
    const alpha = 1 - Math.pow(0.5, 1/half);
    let level = sorted.length ? (sorted[0].value||0) : 0;
    for (const e of sorted){ level = alpha*(e.value||0) + (1-alpha)*level; }
    const currentDow = new Date(now).getDay();
    const score = +(level * seasonalIndex[currentDow]).toFixed(4);
    out.push({ key: k, score, count: arr.length });
  }
  return out;
}
export function estimatePassProb(rows:any[]){
  const vals = rows.map(r=>r.value).filter(v=>typeof v==='number');
  if (!vals.length) return 0.5;
  const pos = vals.filter(v=>v>0).length / vals.length;
  return 0.4 + 0.6*pos;
}
