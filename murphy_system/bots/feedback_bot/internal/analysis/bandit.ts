
export function assignArms(arms?:string[]){ const out:Record<string,string>={}; if(!arms?.length) return out;
  out['assignment'] = arms[Math.floor(Math.random()*arms.length)];
  return out;
}
