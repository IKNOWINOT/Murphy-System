
export function stripJsonComments(s:string){ return s.replace(/\/\*[^]*?\*\//g,'').replace(/(^|\n)\s*\/\/.*(?=\n)/g,''); }
export function parseJson(text:string, strict:boolean){
  try {
    const src = strict ? text : stripJsonComments(text).replace(/,\s*([}\]])/g, '$1');
    return { data: JSON.parse(src), issues: [] as any[] };
  } catch (e:any){
    const msg = `JSON parse error: ${e?.message||e}`;
    if (strict) throw new Error(msg);
    return { data: null, issues: [{ level:'error', message: msg }] };
  }
}
