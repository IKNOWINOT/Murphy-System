
import { InputSchema, OutputSchema, Output } from "./schema";
import { emit } from "./internal/metrics";
import { checkQuota } from "./internal/shim_quota";
import { budgetGuard, chargeCost } from "./internal/shim_budget";
import { computeS, decideAction } from "./internal/shim_stability";
import { selectPath, recordPath } from "./internal/shim_golden_paths";
import { redact } from "./internal/privacy/redactor";
import { getCache, setCache } from "./internal/cache/kv";
import { sha256Base64 } from "./internal/hash/sha256";
import { avgColor, brightness, colorBins } from "./internal/image/stats";
import { simpleSaliency } from "./internal/image/saliency";
import { edgeDensity } from "./internal/image/edges";
import { topColors } from "./internal/image/colors";
import { rms } from "./internal/audio/rms";
import { zcr } from "./internal/audio/zcr";
import { spectralCentroid } from "./internal/audio/centroid";
import { roughTempo } from "./internal/audio/tempo";
import { sampleFrames } from "./internal/video/sample";
import { selectKeyframes } from "./internal/video/keyframes";
import { makeThumbnails } from "./internal/video/thumbnails";
import { summarize as summarizeText } from "./internal/text/summarize";
import { captionImage } from "./internal/model_proxy/caption";
import { ocrImage } from "./internal/model_proxy/ocr";
import { asrAudio } from "./internal/model_proxy/asr";
import { embed } from "./internal/model_proxy/embed";

type Ctx = { userId?: string; tier?: string; kv?: any; db?: any; env?: any; emit?: (e:string,d:any)=>any; logger?: { warn?: Function; error?: Function } };

const KAIA_MIX = { veritas:0.35, vallon:0.2, kiren:0.45 };

function parseJSON(text?:string){ try{ return text ? JSON.parse(text) : null; }catch{ return null; } }
function bytesLen(s?:string){ if(!s) return 0; try{ return atob(s).length; }catch{ return s.length; } }

export async function run(raw: unknown, ctx: Ctx = {}): Promise<Output> {
  const parsed = InputSchema.safeParse(raw);
  if (!parsed.success) { const e:any = new Error("invalid input"); e.status=400; e.details=parsed.error.format(); throw e; }
  const input = parsed.data;
  const tier = (ctx.tier || "free_na").toLowerCase();
  const userId = ctx.userId || "anonymous";
  const params = input.params || {};

  // Quota/budget
  const q = await checkQuota(ctx.kv, userId, tier);
  if (!q.allowed) { await emit("run.blocked",{bot:"multimodal_describer_bot",reason:"quota",tier},ctx); const e:any = new Error("quota"); e.status=429; e.body={reason:"quota"}; throw e; }
  const bg = await budgetGuard(ctx.db, tier);
  if (!bg.allowed) { await emit("run.blocked",{bot:"multimodal_describer_bot",reason:"hard_stop",tier},ctx); const e:any = new Error("hard_stop"); e.status=429; e.body={reason:"hard_stop"}; throw e; }

  const att = input.attachments || [];
  // Enforce size caps
  let totalBytes = 0;
  for (const a of att){ totalBytes += bytesLen(a.bytes_b64) + (a.text? a.text.length : 0); }
  if (params.limits && totalBytes > (params.limits.max_bytes||8000000)){
    const e:any = new Error("too_large"); e.status=413; e.body={reason:"max_bytes"}; throw e;
  }

  // GP reuse key
  const h = await sha256Base64(JSON.stringify({task:input.task,params,attMeta:att.map(a=>({type:a.type,meta:a.metadata||{}}))}));
  const gp = await selectPath(ctx.db, { task_type:"multimodal_describer_bot", params_preview:h.slice(0,32) } as any, 1);
  if (gp?.spec && gp.confidence>=0.9){
    const out: Output = { result: gp.spec, confidence: gp.confidence, notes:["golden_path_reuse"], meta:{ budget:{tier, pool:'gp'}, gp:{hit:true,key:{fp:h},spec_id:gp.id}, stability:{S:1,action:'continue'}, kaiaMix: KAIA_MIX } as any };
    return OutputSchema.parse(out);
  }

  const descriptions:string[] = [];
  const features:any = {};
  let ocr_text:string|undefined = undefined;
  let asr_text:string|undefined = undefined;
  let keyframes:any[]|undefined = undefined;
  const artifacts:{r2_uris:string[]} = { r2_uris: [] };

  // Attempt cache
  const cacheKey = `mm:desc:${h}`;
  const cached = await getCache(ctx.kv, cacheKey);
  if (cached){ const out: Output = { result: cached, confidence: 0.9, notes: ['cache_hit'], meta:{ budget:{cost_usd:0,tier,pool:'mini'}, gp:{hit:false}, stability:{S:1,action:'continue'}, kaiaMix: KAIA_MIX } as any }; return OutputSchema.parse(out); }

  const verbosity = params.verbosity || 'normal';

  for (const a of att){
    if (a.type==='image'){
      const pixels = parseJSON(a.text) as number[][][] | null; // expects HxWx3
      if (pixels && Array.isArray(pixels)){
        const avg = avgColor(pixels);
        const bright = brightness(avg);
        const bins = colorBins(pixels, 5);
        const sal = simpleSaliency(pixels);
        const edge = edgeDensity(pixels);
        descriptions.push(`Image with avg color rgb(${avg.r},${avg.g},${avg.b}), brightness ${bright}, edge_density ${edge}, ${verbosity==='verbose'?'top colors: '+JSON.stringify(topColors(pixels)):''}`.trim());
        features.image = { avg_rgb: avg, brightness: bright, bins, saliency: sal, edge_density: edge };
      } else {
        descriptions.push(`Image (no pixel array provided).`);
        features.image = { note: 'no_pixels' };
      }
      if (input.task==='caption'){
        const cap = await captionImage(ctx, a.bytes_b64? Uint8Array.from(atob(a.bytes_b64),c=>c.charCodeAt(0)) : new Uint8Array(), verbosity as any);
        descriptions.push(cap.caption); 
      }
      if (params.ocr || input.task==='ocr'){
        const res = await ocrImage(ctx, a.bytes_b64? Uint8Array.from(atob(a.bytes_b64),c=>c.charCodeAt(0)) : new Uint8Array());
        ocr_text = (params.privacy?.redact??true) ? redact(res.text) : res.text;
      }
    }
    else if (a.type==='audio'){
      const samples = parseJSON(a.text) as number[] | null; // int amplitude samples
      if (samples && Array.isArray(samples)){
        const r = rms(samples), z = zcr(samples), c = spectralCentroid(samples), bpm = roughTempo(samples);
        descriptions.push(`Audio with RMS ${+r.toFixed(2)}, ZCR ${+z.toFixed(3)}, centroid ${+c.toFixed(2)}, tempo ~${bpm} BPM.`);
        features.audio = { rms:r, zcr:z, centroid:c, tempo:bpm };
      } else {
        descriptions.push(`Audio (no samples provided).`);
        features.audio = { note: 'no_samples' };
      }
      if (params.asr || input.task==='asr'){
        const res = await asrAudio(ctx, a.bytes_b64? Uint8Array.from(atob(a.bytes_b64),c=>c.charCodeAt(0)) : new Uint8Array());
        asr_text = (params.privacy?.redact??true) ? redact(res.text) : res.text;
      }
    }
    else if (a.type==='video'){
      const frames = parseJSON(a.text) as number[][][][] | null; // array of frames: HxWx3 per frame
      if (frames && Array.isArray(frames) && frames.length){
        const samp = sampleFrames(frames, Math.max(1, Math.floor(frames.length/5)));
        const sel = selectKeyframes(frames, params.keyframes?.max||3);
        keyframes = sel.map(k => ({ t:k.t, thumb_uri: `r2://thumb_${k.index}.png` }));
        descriptions.push(`Video: ${frames.length} frames; selected ${sel.length} keyframes.`);
        features.video = { frames: frames.length, keyframes: sel.length };
      } else {
        descriptions.push(`Video (no frames provided).`);
        features.video = { note: 'no_frames' };
      }
    }
    else if (a.type==='text'){
      const short = summarizeText(a.text||'', verbosity as any);
      descriptions.push(`Text: ${short}`);
      features.text = { length: (a.text||'').length };
    }
  }

  // embed task
  if (input.task==='embed'){
    const v = await embed(ctx, att[0]?.bytes_b64? Uint8Array.from(atob(att[0]!.bytes_b64!),c=>c.charCodeAt(0)) : new Uint8Array());
    features['embed'] = { dim: (v.vector||[]).length };
  }

  const result:any = { descriptions, features };
  if (ocr_text) result.ocr_text = ocr_text;
  if (asr_text) result.asr_text = asr_text;
  if (keyframes) result.keyframes = keyframes;
  if (params.store){ result.artifacts = { r2_uris: artifacts.r2_uris }; }

  const latency_ms = 120; const cost_usd = 0.0005;
  const passProb = 0.9;
  const S = computeS(passProb, cost_usd, latency_ms);
  const decision = decideAction(S, { S_min:0.45, gpAvailable: !!gp?.spec });
  await chargeCost(ctx.db, { amount_cents: Math.round(cost_usd*100), tier });

  await setCache(ctx.kv, cacheKey, result, params.cache_ttl_s||900);
  await recordPath(ctx.db, { task_type:'multimodal_describer_bot', key:{ task_type:'multimodal_describer_bot', params_preview:h.slice(0,32) } as any, success:true, confidence:passProb, spec: result });

  const out: Output = { result, confidence: passProb, notes: [], meta:{ budget:{ cost_usd, tier, pool:'mini' }, gp:{ hit:false }, stability:{ S, action: decision.action }, kaiaMix: KAIA_MIX } as any };
  await emit("run.complete",{bot:"multimodal_describer_bot",tier,success:true,task:input.task,latency_ms,cost_usd},ctx);
  return OutputSchema.parse(out);
}

export default { run };
