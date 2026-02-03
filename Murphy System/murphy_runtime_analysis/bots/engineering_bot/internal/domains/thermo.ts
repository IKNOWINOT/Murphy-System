
export function lmtd(spec:any){
  const dT1=spec.dT1||10, dT2=spec.dT2||5;
  const LMTD = (dT1-dT2)/Math.log((dT1)/(dT2));
  return { LMTD };
}
