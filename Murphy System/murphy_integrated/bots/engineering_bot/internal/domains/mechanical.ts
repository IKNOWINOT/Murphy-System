
export function shaftStress(spec:any){
  const T=spec.T||100, J=spec.J||1e-6, r=spec.r||0.01;
  return { tau: T*r/J };
}
