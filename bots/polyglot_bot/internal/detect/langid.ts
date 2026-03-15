
export function detectLang(text:string): {lang:string, confidence:number}{
  const t=(text||'').toLowerCase();
  const tests:[string,RegExp][]=[
    ['ja', /[\u3040-\u30ff\u4e00-\u9faf]/], ['zh', /[\u4e00-\u9fff]/], ['ko', /[\uac00-\ud7af]/],
    ['ru', /[\u0400-\u04FF]/], ['ar', /[\u0600-\u06FF]/], ['he', /[\u0590-\u05FF]/]
  ];
  for (const [lang, re] of tests){ if (re.test(t)) return {lang, confidence:0.95}; }
  if (/[àâçéèêëîïôûùüÿñæœ]/i.test(t)) return {lang:'fr', confidence:0.7};
  if (/[äöüß]/i.test(t)) return {lang:'de', confidence:0.7};
  if (/[áéíóúñ]/i.test(t)) return {lang:'es', confidence:0.7};
  return {lang:'en', confidence:0.6};
}
