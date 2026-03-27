
import { lexScore } from './lexical';
import { rpProject, rpCosine } from '../vector/ann';
import { adaptiveDecay } from '../decay/adaptive';

export async function hybridRank(candidates:any[], query:string, blend:{lexical:number, semantic:number, freshness:number}){
  const qProj = rpProject(query, 64);
  const now = Date.now()/1000;
  const ranked:any[] = [];
  for (const c of candidates){
    const lex = lexScore(c.text||'', query);
    const sem = rpCosine(qProj, c.proj||rpProject(c.text||'',64));
    const fresh = c.last_accessed ? Math.max(0, 1 - ((now - c.last_accessed)/(30*86400))) : 0;
    const retain = adaptiveDecay(c.last_accessed||now, c.access_count||0);
    const score = (blend.lexical*lex + blend.semantic*sem + blend.freshness*fresh) * (c.trust||1) * retain;
    ranked.push({ ...c, score });
  }
  ranked.sort((a,b)=> (b.score||0)-(a.score||0));
  return ranked;
}
