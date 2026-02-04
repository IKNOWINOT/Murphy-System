
export function parseXML(text:string, strict:boolean){
  const issues:any[]=[];
  if (/<!DOCTYPE/i.test(text) || /<!ENTITY/i.test(text)){
    const msg='XML DTD/entities are not allowed (XXE protection)';
    if (strict) throw new Error(msg); issues.push({level:'error', message: msg}); return { data:null, issues };
  }
  const m = text.match(/^\s*<([A-Za-z0-9_:-]+)[^>]*>([\s\S]*)<\/\1>\s*$/);
  if (!m){ const msg='Unsupported XML shape'; if (strict) throw new Error(msg); issues.push({level:'error', message: msg}); return { data:null, issues }; }
  const root=m[1], inner=m[2]; const obj:any={};
  const tagRe=/<([A-Za-z0-9_:-]+)[^>]*>([\s\S]*?)<\/\1>/g; let match;
  while ((match=tagRe.exec(inner))){ obj[match[1]] = match[2].includes('<') ? { '#text': match[2] } : match[2]; }
  const out:any={}; out[root]=obj; return { data: out, issues };
}
