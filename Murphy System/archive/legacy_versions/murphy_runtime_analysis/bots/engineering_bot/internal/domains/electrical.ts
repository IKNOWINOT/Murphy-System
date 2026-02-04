
export function threePhase(spec:any){
  const Vll=spec.Vll||400, I=spec.I||10, pf=spec.pf||0.9;
  const P = Math.sqrt(3)*Vll*I*pf;
  return { P_W: P };
}
