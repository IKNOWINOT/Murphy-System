
import { deriveKEK, genDEK, aesGcmEncrypt, aesGcmDecrypt, b64 } from './kek';
export async function sealKey(plaintext:string, env:{KEK_SECRET:string}){
  const kek = await deriveKEK(env.KEK_SECRET);
  const dek = await genDEK();
  // export DEK raw
  const rawDEK = await crypto.subtle.exportKey('raw', dek);
  const encDEK = await aesGcmEncrypt(kek, new Uint8Array(rawDEK));
  const encKey = await aesGcmEncrypt(dek, new TextEncoder().encode(plaintext));
  return { enc_dek: encDEK, enc_key: encKey };
}
export async function unsealKey(enc_dek:any, enc_key:any, env:{KEK_SECRET:string}){
  const kek = await deriveKEK(env.KEK_SECRET);
  const raw = await aesGcmDecrypt(kek, enc_dek.iv, enc_dek.ct);
  const dek = await crypto.subtle.importKey('raw', raw, { name:'AES-GCM' }, false, ['encrypt','decrypt']);
  const pt = await aesGcmDecrypt(dek, enc_key.iv, enc_key.ct);
  return new TextDecoder().decode(pt);
}
