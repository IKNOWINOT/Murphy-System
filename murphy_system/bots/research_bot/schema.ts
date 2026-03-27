export type Constraints = { safety:'strict'|'normal'|'off'; budget_hint_usd:number; time_s:number; };
export type Source = { url?: string; text?: string; type?: 'html'|'pdf'|'text' };

export interface Input {
  task: string;                               // research question
  params?: {
    sources?: Source[];                        // urls or text
    max_pages?: number;                        // cap fetched pages
    quote_count?: number;                      // desired # of quotes
    style?: { bullets?: boolean; reading_level?: 'hs'|'college'|'pro' };
  };
  constraints?: Constraints;
  context?: { project?: string; topic?: string; user_id?: string; };
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
    answer: string;
    findings: { point: string; quotes: { text: string; source: string }[] }[];
    sources: { url: string; title?: string }[];
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
  const p = obj?.params || {};
  if (p?.sources && !Array.isArray(p.sources)) errors.push('params.sources must be an array');
  return errors.length ? { ok:false, errors } : { ok:true, value: obj as Input };
}
