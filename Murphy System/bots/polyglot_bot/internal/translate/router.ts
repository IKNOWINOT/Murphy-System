
import { detectLang } from '../detect/langid';
import { applyGlossary } from './glossary';
import { stylize } from './style';
import { roundtripScore } from './roundtrip';
import { callModel } from '../shim_model_proxy';

export async function translateBlock(text:string, src:string, tgt:string, style:any, glossary:any, noTranslate:string[]): Promise<{ translated:string; source_lang:string; target_lang:string; quality:number; notes:string[]; translated_flag?:boolean; reason?:string }> {
  const s = src==='auto' ? detectLang(text).lang : src;
  if (s===tgt) return { translated: text, source_lang:s, target_lang:tgt, quality:1.0, notes:['same-language'] };

  // Apply glossary substitutions to input first
  const textWithGlossary = applyGlossary(text, glossary||{}, noTranslate||[]);

  try {
    const messages = [
      { role: 'system' as const, content: `You are a professional translator. Translate the following text from ${s} to ${tgt}. Output only the translated text, preserving formatting.` },
      { role: 'user' as const, content: `Translate the following from ${s} to ${tgt}: ${textWithGlossary}` },
    ];
    const resp = await callModel({ profile: 'mini', messages, json: false, maxTokens: 1024 });
    const translated = resp?.result?.text ?? resp?.data?.text ?? resp?.text ?? '';
    if (!translated) throw new Error('empty response');
    const out = stylize(String(translated), style?.tone||'neutral');
    const q = roundtripScore(text, out);
    return { translated: out, source_lang:s, target_lang:tgt, quality:q, notes: q<0.75 ? ['low-confidence']:[], translated_flag: true };
  } catch {
    // Model unavailable: return original text unchanged with metadata flag
    return { translated: text, source_lang:s, target_lang:tgt, quality:0.0, notes:['model_unavailable'], translated_flag: false, reason: 'model_unavailable' };
  }
}
