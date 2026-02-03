
export function canonicalize(obj:any){
  const sortKeys=(o:any):any=>{
    if (Array.isArray(o)) return o.map(sortKeys);
    if (o && typeof o==='object'){ const out:any={}; for (const k of Object.keys(o).sort()){ out[k]=sortKeys(o[k]); } return out; }
    return o;
  };
  const canon = sortKeys(obj);
  return JSON.stringify(canon);
}
