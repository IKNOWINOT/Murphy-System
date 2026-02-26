
type Msg = { role: 'system'|'user'|'assistant'; content: string };
import { beamDeflection } from './domains/structural';
import { threePhase } from './domains/electrical';
import { reynolds, rocket } from './domains/aero';
import { darcyHead } from './domains/fluids';
import { lmtd } from './domains/thermo';
import { arrhenius } from './domains/chemical';
import { shaftStress } from './domains/mechanical';
import { extrusion } from './domains/printing';
import { costEstimate } from './domains/mfg';
import { rulesFor, PACK_STRUCTURAL, PACK_HVAC, PACK_ELECTRICAL, PACK_AERO, PACK_MFG, register } from './registry/standards';

register(PACK_STRUCTURAL); register(PACK_HVAC); register(PACK_ELECTRICAL); register(PACK_AERO); register(PACK_MFG);

function checksFor(domain:string|undefined, ctx:any){
  const codes:any[] = [], warnings:string[] = [];
  if (!domain) return { codes, warnings };
  for (const r of rulesFor(domain)){
    const ok = r.test(ctx);
    codes.push({ ref:r.ref, ok, severity: r.severity||'info', note:r.note, edition:r.edition, section:r.section });
    if (!ok) warnings.push(`Rule violation: ${r.ref}`);
  }
  return { codes, warnings };
}

export async function callModel(args: { profile: 'mini'|'turbo'; messages: Msg[]; json?: boolean; maxTokens?: number }) {
  const user = args.messages.find(m => m.role === 'user')?.content || '{}';
  let payload: any = {}; try { payload = JSON.parse(user); } catch {}
  const p = payload?.input?.params || {}; const mode = p.mode || 'calc'; const spec = p.spec || {}; const domain = (p.domain || spec.domain || '').toLowerCase();

  let outputs:any={}, steps:any[]=[], artifacts:any[]=[]; let summary='OK', errors:string[]=[];

  try{
    if (mode==='domain' || domain){
      switch(domain){
        case 'structural': { const r=beamDeflection(spec); outputs={...outputs, ...r}; steps.push({name:'beam-deflection', vars:{...spec}}); break; }
        case 'electrical': { const r=threePhase(spec); outputs={...outputs, ...r}; steps.push({name:'three-phase', vars:{...spec}}); break; }
        case 'aero': { const r1=reynolds(spec); outputs={...outputs, ...r1}; if (spec.Isp||spec.m0) { const r2=rocket(spec); outputs={...outputs, ...r2}; steps.push({name:'rocket', vars:{...spec}}); } steps.push({name:'reynolds', vars:{...spec}}); break; }
        case 'fluids': { const r=darcyHead(spec); outputs={...outputs, ...r}; steps.push({name:'darcy', vars:{...spec}}); break; }
        case 'thermo': { const r=lmtd(spec); outputs={...outputs, ...r}; steps.push({name:'lmtd', vars:{...spec}}); break; }
        case 'chemical': { const r=arrhenius(spec); outputs={...outputs, ...r}; steps.push({name:'arrhenius', vars:{...spec}}); break; }
        case 'mechanical': { const r=shaftStress(spec); outputs={...outputs, ...r}; steps.push({name:'shaft-stress', vars:{...spec}}); break; }
        case 'printing': { const r=extrusion(spec); outputs={...outputs, ...r}; steps.push({name:'extrusion', vars:{...spec}}); break; }
        case 'mfg': { const r=costEstimate(spec); outputs={...outputs, ...r}; steps.push({name:'dfm-cost', vars:{...spec}}); break; }
        default: summary='Unknown domain; returning empty outputs';
      }
    } else {
      summary='No-op calc — specify domain/mode'; outputs={};
    }
  } catch(e:any){ errors.push('calc-error: '+String(e)); }

  const chk = checksFor(domain, {...spec, ...outputs});
  const pass = errors.length===0 && chk.warnings.length===0;
  const result = { summary, outputs, steps, checks: { pass, warnings: chk.warnings, errors, codes: chk.codes }, artifacts };
  return { result, usage: { tokens_in: 280, tokens_out: 280, cost_usd: args.profile==='turbo' ? 0.012 : 0.004, model: args.profile } };
}
