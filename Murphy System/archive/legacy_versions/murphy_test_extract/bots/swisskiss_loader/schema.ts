export type Attachment = {
  type: 'code' | 'text' | 'url' | 'manifest' | 'other';
  url?: string;
  text?: string;
  name?: string;
};

export type Constraints = {
  safety: 'strict' | 'normal' | 'off';
  budget_hint_usd: number;
  time_s: number;
};

export type Voice = { stt: boolean; tts: boolean };

export interface Input {
  task: string;
  params?: Record<string, any>;
  attachments?: Attachment[];
  constraints?: Constraints;
  voice?: Voice;
  ghost_profile?: Record<string, any>;
  observations?: Record<string, any>;
  software_signature?: Record<string, any>;
}

export type Pool = 'free' | 'paid' | 'turbo' | 'gp';

export interface BudgetMeta {
  tokens_in?: number;
  tokens_out?: number;
  cost_usd?: number;
  tier: string;
  pool: Pool;
}

export interface GPMeta {
  hit: boolean;
  key?: Record<string, any>;
  spec_id?: string;
}

export interface StabilityMeta {
  S: number;
  action: 'continue' | 'fallback_gp' | 'downgrade' | 'halt';
  drift?: { avg?: number; cur?: number };
}

export interface KaiaMixMeta {
  veritas: number;
  vallon: number;
  kiren: number;
  veritas_vallon: number;
  kiren_veritas: number;
  vallon_kiren: number;
}

export interface Output {
  result: any;
  confidence: number;
  notes?: string;
  meta: {
    budget: BudgetMeta;
    gp: GPMeta;
    stability: StabilityMeta;
    kaiaMix: KaiaMixMeta;
  };
  provenance?: string;
}

export interface ModuleAudit {
  module: string;
  category: string;
  license: string;
  license_ok: boolean;
  requirements: {file: string, size: number}[];
  languages: Record<string, number>;
  risk_scan: { issues: {file: string, pattern: string, pos: number}[], count: number };
  summary: string;
  timestamp?: string;
}

export interface ModuleYaml {
  module_name: string;
  category: string;
  entry_script: string;
  description: string;
  inputs: any[];
  outputs: any[];
  test_command: string | null;
  observer_required: boolean;
}

export function validateInput(obj: any): { ok: true; value: Input } | { ok: false; errors: string[] } {
  const errors: string[] = [];
  if (!obj || typeof obj !== 'object') errors.push('input must be an object');
  if (!obj?.task || typeof obj.task !== 'string') errors.push('task is required string');
  if (obj?.attachments && !Array.isArray(obj.attachments)) errors.push('attachments must be array');
  if (obj?.constraints) {
    const c = obj.constraints;
    if (!['strict', 'normal', 'off'].includes(c.safety)) errors.push('constraints.safety invalid');
    if (typeof c.budget_hint_usd !== 'number' || c.budget_hint_usd < 0) errors.push('constraints.budget_hint_usd invalid');
    if (typeof c.time_s !== 'number' || c.time_s <= 0) errors.push('constraints.time_s invalid');
  }
  return errors.length ? { ok: false, errors } : { ok: true, value: obj as Input };
}
