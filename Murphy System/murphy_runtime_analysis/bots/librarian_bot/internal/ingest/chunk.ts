
import { rpProject } from '../vector/ann';
export function chunkText(text:string, maxLen=1800, overlap=200, projections=64){
  const out:any[]=[]; const t=text||''; if (!t) return out;
  let i=0, ord=0;
  while (i < t.length){
    const end = Math.min(t.length, i+maxLen);
    const slice = t.slice(i, end);
    out.push({ chunk_id: 'c'+ord, ord, text: slice, proj: rpProject(slice, projections) });
    ord++; i = end - overlap;
    if (i<=0) i= end;
  }
  return out;
}
