
export function darcyHead(spec:any){
  const f=spec.f||0.02, L=spec.L||10, D=spec.D||0.1, v=spec.v||2, g=9.80665;
  return { h_loss: f*(L/D)*(v*v/(2*g)) };
}
