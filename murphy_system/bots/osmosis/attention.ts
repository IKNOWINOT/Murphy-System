/**
 * Lightweight attention/probability “matrix” over observed tokens.
 * We transform observations/ghost telemetry into feature tokens,
 * compute counts → softmax weights, and return a ranked list + entropy.
 */

export type Feat = { token: string; c: number };
export type AttentionResult = { ranked: Array<[string, number]>; entropy: number };

function softmax(xs: number[]): number[] {
  const max = Math.max(...xs);
  const exps = xs.map(v => Math.exp(v - max));
  const sum = exps.reduce((a,b)=>a+b,0);
  return exps.map(e => e / (sum || 1));
}

function entropy(ps: number[]): number {
  return -ps.reduce((a,p)=> (p>0 ? a + p*Math.log2(p) : a), 0);
}

export function buildAttention(tokens: string[]): AttentionResult {
  const map = new Map<string, number>();
  for (const t of tokens) map.set(t, (map.get(t) || 0) + 1);
  const feats: Feat[] = Array.from(map.entries()).map(([token, c]) => ({token, c}));
  // weight = softmax(counts)
  const ws = softmax(feats.map(f => f.c));
  const ranked = feats
    .map((f, i) => [f.token, ws[i]] as [string, number])
    .sort((a,b) => b[1] - a[1]);
  return { ranked, entropy: entropy(ws) };
}

/** Normalize Ghost profile + raw observations into tokens */
export function extractTokens(args: {
  task: string;
  ghost?: {
    task_description?: string;
    keystrokes?: Array<[string,string]>;
    mouse_path?: Array<[string, number, number]>;
    active_window?: string;
  };
  observations?: Array<{kind?: string; value?: any;}>;
  signature?: { name?: string; features?: string[]; hints?: string[]; os?: string; version?: string|number; };
}): string[] {
  const toks: string[] = [];

  // Task & ghost description
  if (args.task) toks.push(...args.task.toLowerCase().split(/\W+/).filter(Boolean));
  if (args.ghost?.task_description) toks.push(...args.ghost.task_description.toLowerCase().split(/\W+/).filter(Boolean));
  if (args.ghost?.active_window) toks.push(`window:${args.ghost.active_window.toLowerCase()}`);

  // Keystrokes -> hotkey tokens
  if (args.ghost?.keystrokes) {
    for (const [, key] of args.ghost.keystrokes) {
      const k = key.toLowerCase();
      if (k.includes("ctrl") || k.includes("cmd") || k.includes("alt")) toks.push(`hk:${k}`);
    }
  }

  // Observations kinds/values → coarse tokens
  if (args.observations) {
    for (const o of args.observations) {
      if (o.kind) toks.push(`obs:${o.kind}`);
      if (typeof o.value === "string") {
        const v = o.value.toLowerCase().slice(0,64);
        if (v) toks.push(`val:${v}`);
      }
    }
  }

  // Software signature
  const s = args.signature || {};
  if (s.name) toks.push(`app:${s.name.toLowerCase()}`);
  if (s.os) toks.push(`os:${s.os}`);
  if (Array.isArray(s.features)) toks.push(...s.features.map(f => `feat:${f.toLowerCase()}`));
  if (Array.isArray(s.hints)) toks.push(...s.hints.map(h => `hint:${h.toLowerCase()}`));

  return toks.slice(0, 2048); // keep it compact
}
