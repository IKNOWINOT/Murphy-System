
export function parseJSONArray(text:string, maxObjects:number){
  const out:any[]=[]; try{ const arr=JSON.parse(text); if (Array.isArray(arr)){ for (const el of arr){ out.push(el); if (out.length>=maxObjects) break; } } else { return { items: [], issues:[{level:'error', message:'not an array'}], count:0 }; } }catch(e:any){ return { items: [], issues:[{level:'error', message:'invalid json array'}], count:0 }; }
  return { items: out, issues: [], count: out.length };
}
