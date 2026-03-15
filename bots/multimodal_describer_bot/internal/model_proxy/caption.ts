import { callModel } from '../shim_model_proxy';

export async function captionImage(ctx:any, bytes:Uint8Array, verbosity:'short'|'normal'|'verbose'): Promise<{ caption: string; confidence: number; stub?: boolean; usage: { tokens_in:number; tokens_out:number; cost_usd:number } }> {
  const detail = verbosity === 'short' ? 'one sentence' : verbosity === 'verbose' ? 'detailed multi-sentence description' : 'two or three sentences';
  try {
    const messages = [
      { role: 'system' as const, content: `You are an image captioning engine. Describe the image in ${detail}. Output only the caption text.` },
      { role: 'user' as const, content: JSON.stringify({ image_bytes_length: bytes.length, verbosity }) },
    ];
    const resp = await callModel({ profile: 'turbo', messages, json: false, maxTokens: verbosity === 'verbose' ? 512 : 128 });
    const caption = resp?.result?.caption ?? resp?.result?.text ?? resp?.data?.text ?? resp?.text ?? '';
    if (!caption) throw new Error('empty response');
    const confidence = typeof resp?.confidence === 'number' ? resp.confidence : 0.85;
    return { caption: String(caption), confidence, usage: { tokens_in: resp?.usage?.tokens_in ?? 0, tokens_out: resp?.usage?.tokens_out ?? 0, cost_usd: resp?.usage?.cost_usd ?? 0 } };
  } catch {
    const fallback = verbosity === 'short' ? 'A photo.' : 'An image.';
    return { caption: fallback, confidence: 0.0, stub: true, usage: { tokens_in: 0, tokens_out: 0, cost_usd: 0 } };
  }
}