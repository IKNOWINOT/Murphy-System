
export function extrusion(spec:any){
  const w=spec.width||0.4, h=spec.height||0.2, v=spec.speed||50, k=spec.k||1.0;
  // rough flow rate mm^3/s
  return { Q: k*w*h*v };
}
