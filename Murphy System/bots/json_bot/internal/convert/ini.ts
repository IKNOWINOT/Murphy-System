
export function parseINI(text:string){
  const out:any={}; let section:'__root'|string='__root';
  for (const raw of text.split(/\r?\n/)){
    const line=raw.trim(); if (!line||line.startsWith(';')||line.startsWith('#')) continue;
    const mSec=line.match(/^\[(.+?)\]$/); if (mSec){ section=mSec[1]; out[section]=out[section]||{}; continue; }
    const mKV=line.match(/^([^=]+)=(.*)$/); if (mKV){ const k=mKV[1].trim(); const v=mKV[2].trim(); (out[section]=out[section]||{})[k]=v; }
  }
  if (out['__root'] && Object.keys(out['__root']).length===0) delete out['__root'];
  return { data: out, issues: [] as any[] };
}
