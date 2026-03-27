
export function applyKeyPolicy(obj:any, policy:'none'|'lowercase'|'uppercase'|'snake'|'kebab'='none'){
  if (!obj || typeof obj!=='object') return obj;
  const mapKey=(k:string)=> policy==='lowercase'?k.toLowerCase(): policy==='uppercase'?k.toUpperCase(): policy==='snake'?k.replace(/\W+/g,'_').toLowerCase(): policy==='kebab'?k.replace(/\W+/g,'-').toLowerCase(): k;
  const recur=(x:any):any=>{
    if (Array.isArray(x)) return x.map(recur);
    if (x && typeof x==='object'){ const out:any={}; for (const k of Object.keys(x)){ out[mapKey(k)] = recur(x[k]); } return out; }
    return x;
  };
  return recur(obj);
}
