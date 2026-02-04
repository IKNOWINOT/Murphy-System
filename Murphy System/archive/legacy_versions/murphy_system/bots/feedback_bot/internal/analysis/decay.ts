
export function score(rows:any[], half=3){
  const now = Date.now(); const day=86400e3; const out:any[]=[];
  const group = new Map<string, any[]>();
  for (const r of rows){ const k = `${r.bot}|${r.task_type||""}|${r.meta?.gp_id||""}`; (group.get(k) ?? group.set(k,[]).get(k)).push(r); }
  for (const [k, arr] of group){
    let sum=0, n=0;
    for (const e of arr){
      const ageDays=(now - new Date(e.ts).getTime())/day;
      const decay= Math.pow(0.5, ageDays/half);
      const boost = Math.log1p(e.reinforcement||0);
      sum += (e.value||0) * decay * (1 + 0.1*boost) * (e.weight||1);
      n++;
    }
    const [bot,task_type,gp_id] = k.split("|");
    out.push({ bot, task_type, gp_id: gp_id || undefined, score: +sum.toFixed(4), n });
  }
  return out;
}
