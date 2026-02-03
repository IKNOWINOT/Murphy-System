// src/clockwork/bots/optimizer_core_bot/internal/metrics.ts
export async function emit(event: string, data: any = {}, ctx?: { emit?: (e:string,d:any)=>any }) {
  try { if (ctx?.emit) return ctx.emit(event, data); } catch {}
  try { console.log('[optimizer_core_bot/emit]', event, JSON.stringify(data).slice(0, 2000)); } catch {}
}
