
export async function importKEK(secret: string): Promise<CryptoKey>{
  const enc = new TextEncoder().encode(secret);
  return crypto.subtle.importKey('raw', enc, { name:'PBKDF2' }, false, ['deriveKey']);
}
export async function deriveKEK(secret: string): Promise<CryptoKey>{
  const base = await importKEK(secret);
  const salt = new TextEncoder().encode('clockwork-kek');
  return crypto.subtle.deriveKey(
    { name:'PBKDF2', salt, iterations: 100000, hash:'SHA-256' },
    base,
    { name:'AES-GCM', length: 256 },
    false,
    ['encrypt','decrypt']
  );
}
export async function genDEK(): Promise<CryptoKey>{
  return crypto.subtle.generateKey({ name:'AES-GCM', length:256 }, true, ['encrypt','decrypt']);
}
export function b64(data:ArrayBuffer){ return btoa(String.fromCharCode(...new Uint8Array(data))); }
export function ub64(s:string){ return new Uint8Array(atob(s).split('').map(c=>c.charCodeAt(0))); }
export async function aesGcmEncrypt(key:CryptoKey, plaintext:Uint8Array){
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt({ name:'AES-GCM', iv }, key, plaintext);
  return { iv: b64(iv), ct: b64(ct) };
}
export async function aesGcmDecrypt(key:CryptoKey, iv_b64:string, ct_b64:string){
  const iv = ub64(iv_b64); const ct = ub64(ct_b64);
  const pt = await crypto.subtle.decrypt({ name:'AES-GCM', iv }, key, ct);
  return new Uint8Array(pt);
}
