
export function applyMergePatch(target:any, patch:any){
  if (patch===null) return null;
  if (typeof patch!=='object' || Array.isArray(patch)) return patch;
  if (typeof target!=='object' || target===null) target={};
  for (const k of Object.keys(patch)){
    if (patch[k]===null) delete target[k];
    else target[k]=applyMergePatch(target[k], patch[k]);
  }
  return target;
}
