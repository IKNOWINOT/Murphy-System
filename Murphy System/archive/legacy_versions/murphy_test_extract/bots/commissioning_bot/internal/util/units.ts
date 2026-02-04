// src/clockwork/bots/commissioning_bot/internal/util/units.ts
// Lightweight unit conversion helpers for common commissioning units
const T = { C:'°C', F:'°F' };
const P = { Pa:'Pa', INWC:'in.w.c' };
const FQ = { GPM:'gpm', LPS:'L/s' };

export function convertTemp(value:number, from:string, to:string) {
  const f = from.toLowerCase(); const t = to.toLowerCase();
  if (f === '°f' || f === 'f') {
    const c = (value - 32) * 5/9;
    if (t === '°c' || t === 'c') return c;
    return value; // °F→°F
  }
  if (f === '°c' || f === 'c') {
    const fval = value * 9/5 + 32;
    if (t === '°f' || t === 'f') return fval;
    return value; // °C→°C
  }
  return value;
}

export function convertFlow(value:number, from:string, to:string) {
  const f = from.toLowerCase(); const t = to.toLowerCase();
  if (f === 'gpm' && t === 'l/s') return value * 0.0630902;
  if (f === 'l/s' && t === 'gpm') return value / 0.0630902;
  return value;
}

export function convertPressure(value:number, from:string, to:string) {
  const f = from.toLowerCase(); const t = to.toLowerCase();
  if (f.includes('pa') && t.includes('in')) return value / 249.08891;
  if (f.includes('in') && t.includes('pa')) return value * 249.08891;
  return value;
}

export function normalizePlanUnits(plan:any, desired:Record<string,string>|undefined) {
  if (!desired) return plan;
  const clone = JSON.parse(JSON.stringify(plan));
  for (const p of clone.points || []) {
    if (!p.unit) continue;
    const target = desired[p.unit] || desired[p.unit.toLowerCase()] || undefined;
    if (!target) continue;
    if (p.range?.min != null) p.range.min = convertByUnit(p.range.min, p.unit, target);
    if (p.range?.max != null) p.range.max = convertByUnit(p.range.max, p.unit, target);
    p.unit = target;
  }
  // acceptance targets
  for (const proc of clone.procedures || []) {
    for (const c of proc.acceptance?.criteria || []) {
      if (!c.unit) continue;
      const target = desired[c.unit] || desired[c.unit.toLowerCase()] || undefined;
      if (!target) continue;
      if (Array.isArray(c.target)) {
        c.target = c.target.map((v:any)=>convertByUnit(v, c.unit!, target));
      } else if (typeof c.target === 'number') {
        c.target = convertByUnit(c.target, c.unit!, target);
      }
      c.unit = target;
    }
  }
  return clone;
}

function convertByUnit(value:number, from:string, to:string) {
  const f = from.toLowerCase(); const t = to.toLowerCase();
  // temps
  if ((f.includes('°f') || f==='f' || f==='degf') && (t.includes('°c') || t==='c' || t==='degc')) return convertTemp(value, from, to);
  if ((f.includes('°c') || f==='c' || f==='degc') && (t.includes('°f') || t==='f' || t==='degf')) return convertTemp(value, from, to);
  // flow
  if (f==='gpm' || f==='l/s') return convertFlow(value, from, to);
  // pressure
  if (f.includes('pa') || f.includes('in')) return convertPressure(value, from, to);
  return value;
}
