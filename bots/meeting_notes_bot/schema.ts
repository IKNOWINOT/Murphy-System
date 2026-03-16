export type Constraints = { safety:'strict'|'normal'|'off'; budget_hint_usd:number; time_s:number; };
export type Attachment = { type:'text'|'audio'|'url'; name?:string; url?:string; text?:string };

export interface Input {
  task: string;                                  // e.g., "summarize this meeting"
  params?: {
    title?: string;
    date?: string;                               // ISO
    transcript?: string;
    participants?: string[];
    timezone?: string;
    style?: { bullets?: boolean; };
  };
  attachments?: Attachment[];                    // optional audio/text/url
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
    meeting: { title?:string; date?:string; participants?:string[] };
    summary: string;
    decisions: { text:string; owner?:string }[];
    action_items: { text:string; owner?:string; due?:string; priority?:'low'|'med'|'high' }[];
    risks: string[];
    blockers?: string[];
    next_meeting?: { suggested_date?:string; agenda?:string[] };
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
  if (obj?.attachments && !Array.isArray(obj.attachments)) errors.push('attachments must be an array');
  return errors.length ? { ok:false, errors } : { ok:true, value: obj as Input };
}
