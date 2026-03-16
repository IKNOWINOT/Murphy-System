import { callModel } from '../shim_model_proxy';

export async function asrAudio(ctx:any, bytes:Uint8Array): Promise<{ text: string; confidence: number; stub?: boolean; usage: { tokens_in:number; tokens_out:number; cost_usd:number } }> {
  try {
    const messages = [
      { role: 'system' as const, content: 'You are a speech recognition engine. Transcribe the audio into text. Output only the transcribed text.' },
      { role: 'user' as const, content: JSON.stringify({ audio_bytes_length: bytes.length }) },
    ];
    const resp = await callModel({ profile: 'turbo', messages, json: false, maxTokens: 1024 });
    const text = resp?.result?.text ?? resp?.data?.text ?? resp?.text ?? '';
    if (!text) throw new Error('empty response');
    const confidence = typeof resp?.confidence === 'number' ? resp.confidence : 0.85;
    return { text: String(text), confidence, usage: { tokens_in: resp?.usage?.tokens_in ?? 0, tokens_out: resp?.usage?.tokens_out ?? 0, cost_usd: resp?.usage?.cost_usd ?? 0 } };
  } catch {
    return { text: '[asr unavailable]', confidence: 0.0, stub: true, usage: { tokens_in: 0, tokens_out: 0, cost_usd: 0 } };
  }
}