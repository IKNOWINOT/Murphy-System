
import { allocateKey, revokeKey } from './keys';
import { put as putKV, get as getKV } from '../store/kv';

export async function applyScaling(ctx:any, tenant:string, bot_type:string, from:number, to:number, cooldown_s:number){
  const key = `scale:last_event:${tenant}:${bot_type}`;
  const last = await getKV(ctx.kv, key);
  const now = Date.now();
  if (last && (now - last) < cooldown_s*1000){ return { from, to: from, action:'cooldown_hold' }; }

  if (to>from){
    let success = 0;
    for (let i=0;i<to-from;i++){
      const k = await allocateKey(ctx, tenant, bot_type);
      if (k) success++;
    }
    await putKV(ctx.kv, key, now, cooldown_s);
    return { from, to: from + success, action: success ? 'scale_up' : 'no_keys' };
  } else if (to<from){
    let released = 0;
    for (let i=0;i<from-to;i++){
      const ok = await revokeKey(ctx, tenant, bot_type);
      if (ok) released++;
    }
    await putKV(ctx.kv, key, now, cooldown_s);
    return { from, to: from - released, action: released ? 'scale_down' : 'no_active_instances' };
  }
  return { from, to, action:'hold' };
}
