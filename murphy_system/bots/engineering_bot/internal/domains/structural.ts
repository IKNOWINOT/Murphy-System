
import { convert } from '../util/units_engine';
export function beamDeflection(spec:any){
  const L = spec.span_m ?? convert(spec.span, spec.span_unit||'m', 'm');
  const w = spec.w_N_per_m ?? spec.w ?? 0;
  const E = spec.E_Pa ?? spec.E ?? 200e9;
  const I = spec.I_m4 ?? spec.I ?? 1e-6;
  const d = (5*w*Math.pow(L,4))/(384*E*I);
  return { deflection_m: d, L_over_delta: L/(d||1e-12) };
}
