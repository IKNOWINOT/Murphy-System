
import { histDiff } from './histdiff';
export function selectKeyframes(frames:number[][][][], maxK:number=3){
  const sel:number[]=[0]; let last = frames[0];
  for (let i=1;i<frames.length;i++){
    const d = histDiff(last, frames[i]);
    if (d>5000){ sel.push(i); last = frames[i]; if (sel.length>=maxK) break; }
  }
  return sel.map(i=>({ t:i/30, index:i }));
}
