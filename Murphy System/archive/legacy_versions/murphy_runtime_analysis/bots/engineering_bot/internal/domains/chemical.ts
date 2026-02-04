
export function arrhenius(spec:any){
  const A=spec.A||1e7, Ea=spec.Ea||50000, R=8.314, T=spec.T||350;
  return { k: A*Math.exp(-Ea/(R*T)) };
}
