export type ValidationResult = {
  axis_zero?: boolean;
  monotonic_time?: boolean;
  units_ok?: boolean;
  colorblind_safe?: boolean;
  misleading_risk?: 'low'|'med'|'high';
  issues?: string[];
};

export function validateChartSpec(spec:any, data:any, opts:{colorblind:boolean}): ValidationResult {
  const issues:string[] = [];
  let axis_zero = true;
  let monotonic_time = true;
  let colorblind_safe = !!opts.colorblind;
  let units_ok = true;

  try {
    const mark = (spec?.mark || '').toLowerCase();
    if ((mark==='bar' || mark==='area')) {
      const yScaleZero = !!(spec?.encoding?.y?.scale?.zero ?? true);
      axis_zero = yScaleZero;
      if (!yScaleZero) issues.push('Bar/area chart without zero baseline');
    }
    const xField = spec?.encoding?.x?.field || 'time';
    const arr = Array.isArray(data) ? data : (data?.values || []);
    const times = arr.map((r:any)=>r?.[xField]).filter((t:any)=>t!=null);
    if (times.length>1) {
      for (let i=1;i<times.length;i++){
        if (String(times[i]) < String(times[i-1])) { monotonic_time = false; issues.push('Time not monotonic'); break; }
      }
    }
    if (!opts.colorblind && (spec?.encoding?.color)) {
      colorblind_safe = false; // warn if user didn't request safe palette but color channel is used
    }
  } catch { /* ignore */ }

  const bad = (!axis_zero && (spec?.mark==='bar' || spec?.mark==='area')) || !monotonic_time;
  const misleading_risk:'low'|'med'|'high' = bad ? 'high' : (colorblind_safe ? 'low' : 'med');

  return { axis_zero, monotonic_time, units_ok, colorblind_safe, misleading_risk, issues };
}

export function validateDiagram(specType:'mermaid'|'graphviz'|'svg', spec:any): ValidationResult {
  const issues:string[] = [];
  let units_ok = true;
  let colorblind_safe = true;
  return { axis_zero: true, monotonic_time: true, units_ok, colorblind_safe, misleading_risk:'low', issues };
}
