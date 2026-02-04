
import { detectLang } from '../detect/langid';
import { applyGlossary } from './glossary';
import { stylize } from './style';
import { roundtripScore } from './roundtrip';

export function translateBlock(text:string, src:string, tgt:string, style:any, glossary:any, noTranslate:string[]){
  const s = src==='auto' ? detectLang(text).lang : src;
  if (s===tgt) return { translated: text, source_lang:s, target_lang:tgt, quality:1.0, notes:['same-language'] };
  // Deterministic placeholder translation: wrap text with markers and apply glossary
  let out = `[${tgt}] ` + text;
  out = applyGlossary(out, glossary||{}, noTranslate||[]);
  out = stylize(out, style?.tone||'neutral');
  const q = roundtripScore(text, out);
  return { translated: out, source_lang:s, target_lang:tgt, quality:q, notes: q<0.75? ['low-confidence']:[] };
}
