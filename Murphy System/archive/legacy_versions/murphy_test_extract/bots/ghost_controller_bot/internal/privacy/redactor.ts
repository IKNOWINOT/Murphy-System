
import policy from './policy.json';
export function redact(text: string): string {
  if (!text) return text;
  let out = text;
  for (const pat of policy.deny_patterns){
    try { out = out.replace(new RegExp(pat,'g'), '<redacted>'); } catch {}
  }
  return out;
}
