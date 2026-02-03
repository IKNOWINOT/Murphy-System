
export function reynolds(spec:any){
  const rho=spec.rho||1.225, v=spec.v||10, L=spec.L||1, mu=spec.mu||1.8e-5;
  return { Re: rho*v*L/mu };
}
export function rocket(spec:any){
  const Isp=spec.Isp||300, g0=9.80665, m0=spec.m0||1000, mf=spec.mf||800;
  const dv = g0*Isp*Math.log(m0/mf);
  return { delta_v: dv };
}
