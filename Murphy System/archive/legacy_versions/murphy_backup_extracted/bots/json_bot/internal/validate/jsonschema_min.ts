
export type Issue = { level:'error'|'warn', path:string, message:string };
function typeOf(v:any){ if (v===null) return 'null'; if (Array.isArray(v)) return 'array'; return typeof v; }

export function validate(schema:any, data:any, path:string=''): Issue[] {
  const issues:Issue[]=[];
  if (!schema || typeof schema!=='object') return issues;
  if (schema.type){
    const t=typeOf(data);
    const ok = Array.isArray(schema.type) ? schema.type.includes(t) : t===schema.type;
    if (!ok) issues.push({level:'error', path, message:`type mismatch: expected ${schema.type} got ${t}`});
  }
  if (schema.const !== undefined){
    const ok = JSON.stringify(schema.const)===JSON.stringify(data);
    if (!ok) issues.push({level:'error', path, message:`const mismatch`});
  }
  if (schema.enum){
    const ok = schema.enum.some((e:any)=> JSON.stringify(e)===JSON.stringify(data));
    if (!ok) issues.push({level:'error', path, message:`not in enum`});
  }
  if (schema.minimum!==undefined && typeof data==='number' && data<schema.minimum){
    issues.push({level:'error', path, message:`< minimum ${schema.minimum}`});
  }
  if (schema.maximum!==undefined && typeof data==='number' && data>schema.maximum){
    issues.push({level:'error', path, message:`> maximum ${schema.maximum}`});
  }
  if (schema.pattern && typeof data==='string'){
    try{ const re=new RegExp(schema.pattern); if (!re.test(data)) issues.push({level:'error', path, message:`pattern mismatch`}); }catch{}
  }
  if (schema.required && typeof data==='object' && data && !Array.isArray(data)){
    for (const k of schema.required){ if (!(k in data)) issues.push({level:'error', path, message:`missing required ${k}`}); }
  }
  if (schema.properties && typeof data==='object' && data && !Array.isArray(data)){
    for (const k of Object.keys(data)){
      const sub = schema.properties[k];
      if (sub) issues.push(...validate(sub, data[k], path+'/'+k));
    }
  }
  return issues;
}
