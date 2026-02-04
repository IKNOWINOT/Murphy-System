
export function jsonDiff(a:any, b:any, path:string=''){
  const ops:any[]=[];
  if (a===b) return ops;
  const aIsObj=a&&typeof a==='object', bIsObj=b&&typeof b==='object';
  if (aIsObj && bIsObj && !Array.isArray(a) && !Array.isArray(b)){
    const keys=new Set([...Object.keys(a),...Object.keys(b)]);
    for (const k of keys){ ops.push(...jsonDiff(a[k], b[k], path+'/'+k)); }
    return ops;
  }
  ops.push({ op:'replace', path: path||'/', value: b });
  return ops;
}
export function applyJsonPatch(doc:any, ops:any[]){
  const get=(obj:any, ptr:string)=>{ if (!ptr||ptr==='/') return ['','',obj]; const parts=ptr.split('/').slice(1); let parent:any=null,key=''; let cur=obj; for (const p of parts){ parent=cur; key=p; cur = cur ? cur[p] : undefined; } return [parent,key,cur]; };
  for (const op of ops){
    const [parent,key] = get(doc, op.path);
    if (op.op==='replace'){ if (!parent) return op; parent[key]=op.value; }
    else if (op.op==='add'){ if (!parent) return op; parent[key]=op.value; }
    else if (op.op==='remove'){ if (!parent) return op; delete parent[key]; }
  }
  return doc;
}
