
import { lexScore } from './lexical';
import { rpProject, rpCosine } from '../vector/ann';
// model_proxy bridge (optional): if ctx.env.MODEL_PROXY_URL exists, call it; else RP-based semantic
export async function hybridRank(candidates:any[], query:string, tags:string[], blend:{lexical:number, semantic:number, freshness:number}, opts:{ctx?:any}){
  // compute timestamps freshness boost if provided in candidates.meta.updated_ts
  const now = Date.now();
  const scored:any[]=[];
  const qProj = rpProject(query, 64);
  for (const c of candidates){
    const lex = lexScore(c.text||'', query, tags);
    const sem = rpCosine(qProj, c.proj||rpProject(c.text||'',64));
    const fresh = c.updated_ts ? Math.max(0, 1 - ((now - new Date(c.updated_ts).getTime())/(30*86400e3))) : 0;
    const s = blend.lexical*lex + blend.semantic*sem + blend.freshness*fresh;
    scored.push({ ...c, score: s });
  }
  scored.sort((a,b)=> (b.score||0)-(a.score||0));
  return scored;
}
