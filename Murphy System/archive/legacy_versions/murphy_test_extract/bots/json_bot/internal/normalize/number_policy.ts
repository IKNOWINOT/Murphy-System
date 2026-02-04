
export function applyNumberPolicy(obj:any, policy:'as_is'|'stringify_nonfinite'='as_is'){
  const recur=(x:any):any=>{
    if (Array.isArray(x)) return x.map(recur);
    if (x && typeof x==='object'){ const out:any={}; for (const k of Object.keys(x)){ out[k]=recur(x[k]); } return out; }
    if (typeof x==='number' && !Number.isFinite(x) && policy==='stringify_nonfinite') return String(x);
    return x;
  };
  return recur(obj);
}
