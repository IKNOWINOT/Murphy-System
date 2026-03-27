
export async function signHMAC(secret:string, message:string){
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), {name:'HMAC', hash:'SHA-256'}, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(message));
  const bytes = new Uint8Array(sig); return btoa(String.fromCharCode(...bytes));
}
