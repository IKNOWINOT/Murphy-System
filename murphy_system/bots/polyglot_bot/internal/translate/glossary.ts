
export function applyGlossary(text:string, glossary:Record<string,string>, noTranslate:string[]){
  let out = text;
  for (const nt of noTranslate||[]){
    const re = new RegExp(nt.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'g'); out = out.replace(re, `[[NT:${nt}]]`);
  }
  for (const [k,v] of Object.entries(glossary||{})){
    const re = new RegExp(`\b${k.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}\b`, 'gi');
    out = out.replace(re, v);
  }
  out = out.replace(/\[\[NT:(.+?)\]\]/g, '$1');
  return out;
}
