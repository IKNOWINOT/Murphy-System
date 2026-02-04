
export function thompsonSample(arms:{arm_id:string, alpha:number, beta:number}[]){
  let best = arms[0].arm_id, bestS = -1;
  for (const a of arms){
    const s = betaSample(a.alpha, a.beta);
    if (s>bestS){ bestS=s; best=a.arm_id; }
  }
  return best;
}
function betaSample(alpha:number, beta:number){
  // crude: average of uniforms to approximate beta draw
  const n=6; let s=0; for (let i=0;i<n;i++){ s += Math.random(); }
  const u = s/n;
  // map uniform to beta via inverse CDF approx (placeholder): use power heuristic
  return Math.pow(u, 1/alpha) * Math.pow(1-u, 1/beta);
}
