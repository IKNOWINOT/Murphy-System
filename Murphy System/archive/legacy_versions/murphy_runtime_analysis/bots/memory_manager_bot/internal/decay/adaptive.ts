
export function adaptiveDecay(last_accessed:number, access_count:number, decay_factor:number=1.8){
  const age_days = Math.max(0, (Date.now()/1000 - last_accessed)/86400);
  const stability = access_count>0 ? Math.pow(access_count, decay_factor) : 1.0;
  return Math.exp(-age_days / stability);
}
