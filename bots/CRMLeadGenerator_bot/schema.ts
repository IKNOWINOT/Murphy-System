export type Constraints = { safety:'strict'|'normal'|'off'; budget_hint_usd:number; time_s:number };
export type Lead = { email?:string; name?:string; title?:string; company?:string; domain?:string; phone?:string; source?:string; tags?:string[]; custom?:Record<string,any> };
export type Contact = Lead & { id?:string; owner?:string };
export type Company = { domain?:string; name?:string; size?:string; industry?:string; id?:string };
export type Deal = { id?:string; company_domain?:string; title?:string; amount?:number; stage?:string; pipeline?:string; owner?:string };
export type Campaign = { id?:string; name:string; objective:'outbound'|'inbound'|'ads'|'social'; segment?:Record<string,any>; utm?:Record<string,string> };
export type SequenceStep = { channel:'email'|'sms'|'social'; delay_h:number; template_id?:string; copy?:{subject?:string; body?:string; text?:string} };
export type Sequence = { id?:string; name:string; steps: SequenceStep[] };
export type AssetSpec = { emails?: any[]; landing?: { html?: string; spec?: any }; ads?: { platform:string; headline:string; body:string; url:string }[] };

export interface Input {
  task: string;
  params?: {
    action:
      'discover'|'ingest'|'verify_emails'|'clean_list'|'mailbox_sync'|'opt_in'|'opt_out'|
      'upsert_contact'|'upsert_company'|'create_deal'|'score'|'generate_assets'|'enroll'|'launch_campaign'|'log_activity'|'search'|'unsubscribe'|'report';
    sources?: { url?: string; html?: string; text?: string; domain_hint?: string }[];
    allow_scrape?: boolean;
    leads?: Lead[];
    contact?: Contact;
    company?: Company;
    deal?: Deal;
    campaign?: Campaign;
    sequence?: Sequence;
    assets?: AssetSpec;
    filters?: Record<string,any>;
    owner?: string;
    execute?: boolean;
    dry_run?: boolean;
    data?: { csv?: string };
    style?: { tone?: 'formal'|'casual'|'persuasive'|'technical' };
    mailbox_id?: string;
    reason?: string;
  };
  constraints?: Constraints;
  context?: { project?:string; topic?:string; user_id?:string };
  software_signature?: Record<string, any>;
}

export type Pool = 'free'|'paid'|'turbo'|'gp';
export interface BudgetMeta { tokens_in?:number; tokens_out?:number; cost_usd?:number; tier:string; pool:Pool }
export interface GPMeta { hit:boolean; key?:Record<string,any>; spec_id?:string }
export interface StabilityMeta { S:number; action:'continue'|'fallback_gp'|'downgrade'|'halt'; drift?:{avg?:number;cur?:number} }
export interface KaiaMixMeta { veritas:number; vallon:number; kiren:number; veritas_vallon:number; kiren_veritas:number; vallon_kiren:number }

export interface Output {
  result: any;
  confidence: number;
  notes?: string;
  meta: { budget: BudgetMeta; gp: GPMeta; stability: StabilityMeta; kaiaMix: KaiaMixMeta };
  provenance?: string;
}

export function validateInput(obj:any): { ok:true; value:Input } | { ok:false; errors:string[] } {
  const errors:string[] = [];
  if (!obj || typeof obj !== 'object') errors.push('input must be an object');
  if (!obj?.task || typeof obj.task !== 'string') errors.push('task is required string');
  return errors.length ? { ok:false, errors } : { ok:true, value: obj as Input };
}
