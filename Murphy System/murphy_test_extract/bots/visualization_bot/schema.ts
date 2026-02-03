export type Attachment = { type: 'code'|'text'|'url'|'manifest'|'other'; url?:string; text?:string; name?:string; };

export type Constraints = { safety:'strict'|'normal'|'off'; budget_hint_usd:number; time_s:number; };

export interface Input {
  task: string;
  params?: {
    kind?: 'chart'|'diagram'|'cad_scope'|'model3d';
    spec?: any;
    data?: any;
    style?: { theme?:string; colorblind_safe?:boolean; show_grid?:boolean; };
    export?: { svg?: boolean; png?: { w:number; h:number } };
    annotations?: any;
  };
  attachments?: Attachment[];
  constraints?: Constraints;
  context?: { project?:string; topic?:string; user_id?:string; };
  software_signature?: Record<string, any>;
}

export type Pool = 'free'|'paid'|'turbo'|'gp';

export interface BudgetMeta { tokens_in?:number; tokens_out?:number; cost_usd?:number; tier:string; pool:Pool; }

export interface GPMeta { hit:boolean; key?:Record<string,any>; spec_id?:string; }

export interface StabilityMeta { S:number; action:'continue'|'fallback_gp'|'downgrade'|'halt'; drift?:{avg?:number;cur?:number}; }

export interface KaiaMixMeta {
  veritas:number; vallon:number; kiren:number;
  veritas_vallon:number; kiren_veritas:number; vallon_kiren:number;
}

export interface Output {
  result: {
    visual_id: string;
    spec_type: 'svg'|'vega-lite'|'mermaid'|'graphviz'|'gltf';
    spec: any;
    png_url?: string;
    validations: {
      axis_zero?: boolean; monotonic_time?: boolean; units_ok?: boolean; colorblind_safe?: boolean;
      misleading_risk?: 'low'|'med'|'high'; issues?: string[];
    };
    collab?: { cad?: any; simulation?: any; };
  };
  confidence: number;
  notes?: string;
  meta: { budget: BudgetMeta; gp: GPMeta; stability: StabilityMeta; kaiaMix: KaiaMixMeta; };
  provenance?: string;
}

export function validateInput(obj:any): {ok:true; value:Input} | {ok:false; errors:string[]} {
  const errors:string[] = [];
  if (!obj || typeof obj !== 'object') errors.push('input must be an object');
  if (!obj?.task || typeof obj.task !== 'string') errors.push('task is required string');
  if (obj?.constraints) {
    const c = obj.constraints;
    if (!['strict','normal','off'].includes(c.safety)) errors.push('constraints.safety invalid');
    if (typeof c.budget_hint_usd !== 'number' || c.budget_hint_usd < 0) errors.push('constraints.budget_hint_usd invalid');
    if (typeof c.time_s !== 'number' || c.time_s <= 0) errors.push('constraints.time_s invalid');
  }
  return errors.length ? { ok:false, errors } : { ok:true, value: obj as Input };
}
