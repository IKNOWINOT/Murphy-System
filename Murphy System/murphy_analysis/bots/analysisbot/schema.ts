export type Constraints = { safety:'strict'|'normal'|'off'; budget_hint_usd:number; time_s:number; };
export type Table = { name:string; columns:{ name:string; type?:string }[]; pk?:string[] };
export type Schema = { dialect?: 'postgres'|'mysql'|'sqlite'|'mssql'|'duckdb'|'bigquery'; tables: Table[] };

export interface Input {
  task: string;                               // e.g., "How many orders per month in 2024?"
  params?: {
    question?: string;                        // natural language
    dialect?: 'postgres'|'mysql'|'sqlite'|'mssql'|'duckdb'|'bigquery';
    schema?: Schema;                          // optional inline schema
    db?: { id: string };                      // connection identifier for adapter
    execute?: boolean;                        // default false (dry-run)
    max_rows?: number;                        // default 200
    sample?: boolean;                         // if true, add LIMIT even if execute=false for preview
    style?: { summarize?: boolean; };
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
    sql: string;
    rationale?: string;
    warnings?: string[];
    executed?: boolean;
    rows?: any[];
    columns?: string[];
    row_count?: number;
    profile?: { nulls?: Record<string, number>; minmax?: Record<string, {min?:any,max?:any}> };
    summary?: string;
    schema_used?: Schema;
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
  if (p?.schema && (!p.schema.tables || !Array.isArray(p.schema.tables))) errors.push('params.schema.tables must be an array');
  return errors.length ? { ok:false, errors } : { ok:true, value: obj as Input };
}
