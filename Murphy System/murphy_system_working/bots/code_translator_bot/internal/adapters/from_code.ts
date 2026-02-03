// src/clockwork/bots/code_translator_bot/internal/adapters/from_code.ts
import type { Input } from '../../schema';
export function fromCodingBot(evt: any): Input {
  const task = evt?.intent || 'refactor and add tests';
  const attachments = evt?.files?.map((f:any)=>({ type:'text', text:String(f.content||''), filename:f.name })) || [];
  return { task, attachments, params: { filename: evt?.files?.[0]?.name, src_lang: evt?.lang } };
}
