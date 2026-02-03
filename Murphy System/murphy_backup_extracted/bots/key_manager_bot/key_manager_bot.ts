
import { InputSchema, OutputSchema, Output } from './schema';
import { emit } from './internal/metrics';
import { checkQuota } from './internal/shim_quota';
import { budgetGuard, chargeCost } from './internal/shim_budget';
import { computeS, decideAction } from './internal/shim_stability';
import * as dbKeys from './internal/db/keys';
import * as dbPolicies from './internal/db/policies';
import * as usage from './internal/db/usage';
import * as audit from './internal/db/audit';
import { sealKey, unsealKey } from './internal/crypto/envelope';
import { signHMAC } from './internal/crypto/hmac';

type Ctx = { userId?: string; tier?: string; kv?: any; db?: D1Database; env?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

const KAIA_MIX = { veritas:0.35, vallon:0.5, kiren:0.15 };

export async function run(raw: unknown, ctx: Ctx = {}): Promise<Output> {
  const parsed = InputSchema.safeParse(raw);
  if (!parsed.success) { const e:any = new Error('invalid input'); e.status=400; e.details=parsed.error.format(); throw e; }
  const input = parsed.data;

  const userId = ctx.userId || 'anonymous';
  const tier = (ctx.tier || 'free_na').toLowerCase();

  // Guards
  const q = await checkQuota(ctx.kv, userId, tier);
  if (!q.allowed) { await emit('run.blocked',{bot:'key_manager_bot',reason:'quota',tier},ctx); const e:any = new Error('quota'); e.status=429; e.body={reason:'quota'}; throw e; }
  const bg = await budgetGuard(ctx.db, tier);
  if (!bg.allowed) { await emit('run.blocked',{bot:'key_manager_bot',reason:'hard_stop',tier},ctx); const e:any = new Error('hard_stop'); e.status=429; e.body={reason:'hard_stop'}; throw e; }

  const p = input.params||{};
  const nowIso = new Date().toISOString();

  let artifact:any = undefined;
  let signature:any = undefined;
  let policy:any = undefined;
  let report:any = undefined;

  // Tasks
  if (input.task==='register_key'){
    if (!p.key_value || !p.key_id || !p.bot_name || !p.scope) throw new Error('missing params');
    const sealed = await sealKey(p.key_value, { KEK_SECRET: ctx.env?.KEK_SECRET || 'dev-secret' });
    await dbKeys.insertKey(ctx.db!, {
      id: p.key_id, bot_name: p.bot_name, scope: p.scope, status:'active',
      enc_dek: sealed.enc_dek, enc_key: sealed.enc_key, key_version:1,
      created_ts: nowIso, last_used_ts: nowIso, usage_count:0, meta_json:{}
    });
    await audit.audit(ctx.db!, 'key.register', userId, { bot_name:p.bot_name, scope:p.scope, key_id:p.key_id });
    artifact = { sealed: true };
  }

  if (input.task==='allocate_key'){
    if (!p.bot_name) throw new Error('missing bot_name');
    const id = await dbKeys.allocateUnassigned(ctx.db!, p.bot_name);
    artifact = { key_id: id };
  }

  if (input.task==='policy_set'){
    if (!p.bot_name || !p.scope || !p.policy) throw new Error('missing params');
    await dbPolicies.upsertPolicy(ctx.db!, p.bot_name, p.scope, p.policy);
    policy = p.policy;
  }

  if (input.task==='policy_get'){
    if (!p.bot_name || !p.scope) throw new Error('missing params');
    const row = await dbPolicies.getPolicy(ctx.db!, p.bot_name, p.scope);
    policy = row ? { max_calls:row.max_calls, window_s:row.window_s, burst:row.burst, tier: row.tier } : null;
  }

  if (input.task==='mint_ephemeral'){
    if (!p.bot_name || !p.scope) throw new Error('missing params');
    const exp = Date.now() + (p.ttl_s||300)*1000;
    const payload = JSON.stringify({ sub:p.bot_name, scope:p.scope, exp });
    const sig = await signHMAC(ctx.env?.EPHEMERAL_SECRET || 'ephemeral', payload);
    artifact = { ephemeral_token: btoa(payload), signature: sig, expires_ts: new Date(exp).toISOString() };
  }

  if (input.task==='use_key'){
    if (!p.bot_name || !p.scope || !p.key_id) throw new Error('missing params');
    const polRow = await dbPolicies.getPolicy(ctx.db!, p.bot_name, p.scope) || { max_calls:100, window_s:60, burst:20 };
    const gate = await usage.checkAndConsume(ctx.kv, `rk:${p.bot_name}:${p.scope}:${p.key_id}`, polRow.max_calls, polRow.window_s, polRow.burst);
    if (!gate.allowed) { await audit.audit(ctx.db!, 'key.rate_limit.block', userId, {bot_name:p.bot_name, scope:p.scope, key_id:p.key_id}); const e:any=new Error('rate_limited'); e.status=429; e.body={reason:'rate_limited', resetAt:gate.resetAt}; throw e; }
    await dbKeys.incrementUsage(ctx.db!, p.key_id);
    // do not return plaintext; mint short token for downstream
    const exp = Date.now() + 5*60*1000;
    const payload = JSON.stringify({ sub:p.bot_name, scope:p.scope, kid:p.key_id, exp });
    const sig = await signHMAC(ctx.env?.EPHEMERAL_SECRET || 'ephemeral', payload);
    artifact = { ephemeral_token:btoa(payload), signature:sig, expires_ts: new Date(exp).toISOString() };
  }

  if (input.task==='get_key'){
    if (!p.key_id) throw new Error('missing key_id');
    const row:any = await dbKeys.selectKey(ctx.db!, p.key_id);
    if (!row || row.status!=='active') throw new Error('not_found_or_inactive');
    if (!p.allow_plaintext_get) {
      artifact = { sealed_key: true, key_version: row.key_version };
    } else {
      const key = await unsealKey(JSON.parse(row.enc_dek), JSON.parse(row.enc_key), { KEK_SECRET: ctx.env?.KEK_SECRET || 'dev-secret' });
      artifact = { plaintext_key: key };
    }
  }

  if (input.task==='revoke_key' || input.task==='quarantine_key' || input.task==='rotate_key'){
    if (!p.key_id) throw new Error('missing key_id');
    const status = input.task==='revoke_key' ? 'revoked' : input.task==='quarantine_key' ? 'quarantined' : 'active';
    await dbKeys.updateStatus(ctx.db!, p.key_id, status);
    await audit.audit(ctx.db!, `key.${input.task}`, userId, { key_id:p.key_id });
    artifact = { status };
  }

  if (input.task==='sign_request'){
    if (!p.request) throw new Error('missing request');
    const ts = Date.now().toString();
    const msg = [p.request.method||'GET', p.request.url||'', ts].join('\n');
    const sig = await signHMAC(ctx.env?.REQUEST_SIGN_SECRET || 'req', msg);
    signature = { alg:'HMAC-SHA256', headers: { 'X-Signature': sig, 'X-Timestamp': ts } };
  }

  if (input.task==='audit_report'){
    report = { usage: 'rollup_pending', entropy: 0.0 };
  }

  // Stability & budget
  const latency_ms = 100; const cost_usd = 0.0005;
  const passProb = 0.95; const S = computeS(passProb, cost_usd, latency_ms);
  const decision = decideAction(S, { S_min:0.45, gpAvailable:false });
  await chargeCost(ctx.db, { amount_cents: Math.round(cost_usd*100), tier });

  const out = {
    result: { status:'ok', artifact, signature, policy, report },
    confidence: 0.95,
    notes: [],
    meta: { budget:{cost_usd, tier, pool:'mini'}, gp:{hit:false}, stability:{S, action:decision.action}, kaiaMix: KAIA_MIX }
  } as any;
  await emit('run.complete',{bot:'key_manager_bot',tier,success:true,task:input.task,latency_ms,cost_usd},ctx);
  return OutputSchema.parse(out);
}

export default { run };
