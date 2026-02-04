
export function computeS(passProb:number,costUsd:number,latencyMs:number, w={qw:0.7,cw:0.2,lw:0.1}, ref={cr:0.01, lr:1.5}){
  const nc=(costUsd||0)/ref.cr; const nl=(latencyMs/1000)/ref.lr; const pp=Math.max(0,Math.min(1,passProb||0));
  return Math.max(-1, Math.min(1, w.qw*pp - w.cw*nc - w.lw*nl ));
}
export function decideAction(S:number,o:{S_min?:number,gpAvailable?:boolean}={}){
  const m=o.S_min??0.45; const gp=!!o.gpAvailable; if(S>=m) return {S,action:'continue' as const}; if(gp) return {S,action:'fallback_gp' as const}; return {S,action:'downgrade' as const};
}
