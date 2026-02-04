
export type Rule = { domain: string; ref: string; edition?: string; section?: string; severity?: 'info'|'warn'|'critical'; note?: string; test:(ctx:any)=>boolean };

const registry: Rule[] = [];

export function register(pack: Rule[]){ registry.push(...pack); }
export function rulesFor(domain:string){ return registry.filter(r => r.domain.toLowerCase()===domain.toLowerCase()); }

// Sample packs
export const PACK_STRUCTURAL: Rule[] = [
  { domain:'structural', ref:'AISC-L/360-Deflection', edition:'heuristic', section:'deflection', severity:'warn', note:'span/deflection >= 360', test:(c)=> (c?.span && c?.deflection)? ((c.span/(c.deflection||1e-9))>=360): true },
  { domain:'structural', ref:'Bolt-Safety-Factor>=2', edition:'heuristic', section:'bolted-joint', severity:'critical', test:(c)=> (c?.bolt_sf? c.bolt_sf>=2 : true) }
];

export const PACK_HVAC: Rule[] = [
  { domain:'hvac', ref:'ASHRAE-DuctVelocity', edition:'heuristic', section:'ducts', severity:'warn', note:'< 12 m/s typical', test:(c)=> (c?.vel? c.vel<12 : true) }
];

export const PACK_ELECTRICAL: Rule[] = [
  { domain:'electrical', ref:'NEC-VoltageDrop', edition:'heuristic', section:'branch-circuit', severity:'warn', note:'< 3% recommended', test:(c)=> (c?.v_drop? c.v_drop<0.03 : true) }
];

export const PACK_AERO: Rule[] = [
  { domain:'aero', ref:'Subsonic-Mach<1', edition:'heuristic', section:'flight', severity:'warn', test:(c)=> (c?.mach? c.mach<1 : true) }
];

export const PACK_MFG: Rule[] = [
  { domain:'mfg', ref:'Fastener-Type-Limit', edition:'heuristic', section:'dfma', severity:'warn', note:'<= 3 fastener types', test:(c)=> (Array.isArray(c?.fastener_types)? new Set(c.fastener_types).size<=3 : true) }
];
